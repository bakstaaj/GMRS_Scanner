from __future__ import annotations
import argparse, csv, json, subprocess, threading, time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from . import PRODUCT_NAME, VERSION, REQUIRED_RTL_SERIAL
from .channels import GMRS_CHANNELS, channel_for_number
from .fft_scan import FftPoint, MIN_VALID_SNR_DB, score_channels, simulated_spectrum

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "web"
RUNTIME = ROOT / "runtime"
INPUT_RATE_HZ, OUTPUT_RATE_HZ = 240_000, 24_000
LOCK_HOLD_SECONDS = 8.0
NO_SIGNAL_WAIT_SECONDS = 2.0

class RadioState:
    def __init__(self, simulate: bool = False) -> None:
        self.simulate = simulate; self.lock = threading.RLock()
        self.settings_path = RUNTIME / "settings.json"
        self.settings = {"rtl_serial": REQUIRED_RTL_SERIAL, "rf_gain_db": 40.0, "channel_controls": {}, "registration": {}}
        self._load_settings(); self.points = []; self.candidates = []; self.tuned = None; self.tune_frequency_hz = None; self.running = False; self.manual_tuned = False; self.audio_process = None; self.scan_thread = None; self.scan_stop = threading.Event(); self.rescan_event = threading.Event(); self.first_scan_event = threading.Event(); self.scan_generation = 0; self.scan_cycles = 0

    def _load_settings(self) -> None:
        try:
            saved = json.loads(self.settings_path.read_text(encoding="utf-8")); self.settings.update({key: saved[key] for key in ("rtl_serial", "rf_gain_db") if key in saved})
            if isinstance(saved.get("channel_controls"), dict): self.settings["channel_controls"] = saved["channel_controls"]
            if isinstance(saved.get("registration"), dict): self.settings["registration"] = saved["registration"]
        except (OSError, ValueError, TypeError): pass

    def _save_settings(self) -> None:
        RUNTIME.mkdir(parents=True, exist_ok=True); temporary = self.settings_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.settings, indent=2) + "\n", encoding="utf-8"); temporary.replace(self.settings_path)

    def control(self, number: int) -> dict:
        value = self.settings["channel_controls"].get(str(number), {})
        if value.get("mode") == "block": return {"mode": "block"}
        if value.get("mode") == "skip":
            until = float(value.get("until", 0))
            if until > time.time(): return {"mode": "skip", "until": until, "remaining_seconds": max(0, int(until - time.time()))}
            self.settings["channel_controls"].pop(str(number), None)
        return {"mode": "active"}

    def channel_payload(self) -> list[dict]:
        return [{**channel.as_dict(), "scan_control": self.control(channel.number)} for channel in GMRS_CHANNELS]

    def available(self) -> list[dict]:
        return [channel.as_dict() for channel in GMRS_CHANNELS if self.control(channel.number)["mode"] == "active"]

    def stop(self) -> None:
        self.scan_generation += 1
        self.scan_stop.set()
        self.rescan_event.set()
        process = self.audio_process
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: process.kill()
        self.audio_process = None; self.running = False

    def _scan_once(self, generation: int) -> None:
        with self.lock:
            if generation != self.scan_generation or self.scan_stop.is_set(): return
            self._stop_audio_only()
            channels = self.available()
        points = simulated_spectrum(channels) if self.simulate else self._rtl_power_spectrum()
        candidates = score_channels(points, channels)
        winner = candidates[0] if candidates and candidates[0].snr_db >= MIN_VALID_SNR_DB else None
        with self.lock:
            if generation != self.scan_generation or self.scan_stop.is_set(): return
            self.points = points; self.candidates = candidates; self.tuned = winner.channel if winner else None; self.tune_frequency_hz = winner.peak_frequency_hz if winner else None; self.scan_cycles += 1; self.first_scan_event.set()
            if winner: self._start_audio_only(winner.channel)

    def _scanner_loop(self, generation: int) -> None:
        while generation == self.scan_generation and not self.scan_stop.is_set():
            self._scan_once(generation)
            if generation != self.scan_generation or self.scan_stop.is_set(): break
            with self.lock: lock_found = self.tuned is not None
            self.rescan_event.wait(LOCK_HOLD_SECONDS if lock_found else NO_SIGNAL_WAIT_SECONDS)
            self.rescan_event.clear()
        with self.lock:
            if generation == self.scan_generation and self.scan_stop.is_set(): self.running = False

    def start_scanner(self) -> dict:
        with self.lock:
            if self.scan_thread and self.scan_thread.is_alive(): return self.snapshot()
            self.scan_generation += 1; generation = self.scan_generation; self.scan_stop = threading.Event(); self.rescan_event = threading.Event(); self.first_scan_event = threading.Event(); self.running = True; self.manual_tuned = False
            self.scan_thread = threading.Thread(target=self._scanner_loop, args=(generation,), name="gmrs-scanner-loop", daemon=True); self.scan_thread.start()
        self.first_scan_event.wait(21)
        return self.snapshot({"scanner_started": True})

    def _stop_audio_only(self) -> None:
        process = self.audio_process
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: process.kill()
        self.audio_process = None

    def _rtl_power_spectrum(self) -> list[FftPoint]:
        RUNTIME.mkdir(parents=True, exist_ok=True); output = RUNTIME / "gmrs-spectrum.csv"; output.unlink(missing_ok=True)
        command = ["rtl_power", "-d", str(self.settings["rtl_serial"]), "-f", "462550000:467725000:2500", "-i", "0.25", "-1", "-g", str(self.settings["rf_gain_db"]), str(output)]
        try: result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.SubprocessError): return []
        if result.returncode != 0 or not output.is_file(): return []
        points = []
        for fields in csv.reader(output.read_text(encoding="utf-8", errors="replace").splitlines()):
            if len(fields) < 7: continue
            try: start, step = float(fields[2]), float(fields[4]); powers = [float(v) for v in fields[6:]]
            except ValueError: continue
            scale = 1 if start > 1_000_000 else 1_000_000
            points.extend(FftPoint(int((start + i * step) * scale), power) for i, power in enumerate(powers))
        return points

    def _start_audio(self, channel: dict) -> None:
        self.stop(); self._start_audio_only(channel); self.running = True

    def _start_audio_only(self, channel: dict) -> None:
        command = ["rtl_fm", "-d", str(self.settings["rtl_serial"]), "-f", str(channel["frequency_hz"]), "-M", "fm", "-s", str(INPUT_RATE_HZ), "-r", str(OUTPUT_RATE_HZ), "-g", str(self.settings["rf_gain_db"]), "-l", "0", "-p", "0", "-E", "offset", "-E", "dc", "-E", "deemp"]
        try: self.audio_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError: self.audio_process = None

    def scan(self) -> dict:
        return self.start_scanner()

    def tune(self, number: int) -> dict:
        with self.lock:
            channel = channel_for_number(number).as_dict(); self.scan_generation += 1; self.scan_stop.set(); self.rescan_event.set(); self._stop_audio_only(); self.tuned = channel; self.tune_frequency_hz = channel["frequency_hz"]; self.manual_tuned = True; self.running = True
            if not self.simulate: self._start_audio_only(channel)
            return self.snapshot()

    def set_control(self, number: int, mode: str) -> dict:
        if mode not in ("active", "skip", "block"): raise ValueError("mode must be active, skip, or block")
        with self.lock:
            if mode == "active": self.settings["channel_controls"].pop(str(number), None)
            elif mode == "skip": self.settings["channel_controls"][str(number)] = {"mode": "skip", "until": time.time() + 300}
            else: self.settings["channel_controls"][str(number)] = {"mode": "block"}
            self._save_settings(); return self.snapshot()

    def control_current(self, action: str) -> dict:
        with self.lock:
            if not self.tuned: return self.snapshot({"error": "There is no currently locked channel."})
            number = int(self.tuned["number"])
        if action not in ("skip", "block", "clear"): raise ValueError("action must be skip, block, or clear")
        result = self.set_control(number, "active" if action == "clear" else action)
        with self.lock:
            should_resume = self.running and self.manual_tuned
            if self.running and not self.manual_tuned: self.rescan_event.set()
            if should_resume: self.scan_thread = None
        return self.start_scanner() if should_resume else result

    def clear_all_controls(self) -> dict:
        with self.lock:
            self.settings["channel_controls"] = {}
            self._save_settings()
            if self.running and not self.manual_tuned: self.rescan_event.set()
            return self.snapshot()

    def activate_license(self, license_serial: str, email: str) -> dict:
        raw_serial = f"{int(self.settings['rtl_serial']):016X}"
        installation_serial = "N0JCG-" + "-".join(raw_serial[i:i + 4] for i in range(0, 16, 4))
        payload = json.dumps({"license_serial": license_serial, "email": email, "installation_serial": installation_serial, "product_slug": "gmrs-scanner", "app_version": VERSION}).encode()
        request = urllib.request.Request("https://www.n0jcg.com/api/v1/licenses/validate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response: result = json.loads(response.read().decode("utf-8"))
        except Exception as error: raise ValueError(f"licensing service unavailable: {error}")
        if not result.get("valid"): raise ValueError(result.get("error") or result.get("reason") or "license rejected")
        self.settings["registration"] = {"registered": True, "license_suffix": result.get("license_suffix", ""), "serial_number": installation_serial, "email": email}
        self._save_settings(); return self.snapshot()

    def snapshot(self, extra: dict | None = None) -> dict:
        tuned = dict(self.tuned) if self.tuned else None
        if tuned: tuned["scan_control"] = self.control(int(tuned["number"]))
        if tuned and self.tune_frequency_hz: tuned.update({"tuned_frequency_hz": self.tune_frequency_hz, "offset_hz": self.tune_frequency_hz - tuned["frequency_hz"]})
        result = {"ok": True, "product": PRODUCT_NAME, "version": VERSION, "simulate": self.simulate, "rtl_serial": self.settings["rtl_serial"], "running": self.running, "manual_tuned": self.manual_tuned, "scan_cycles": self.scan_cycles, "tuned": tuned, "registration": self.settings.get("registration", {}), "channels": self.channel_payload(), "candidates": [{"channel": c.channel, "peak_frequency_hz": c.peak_frequency_hz, "peak_dbfs": c.peak_dbfs, "noise_floor_dbfs": c.noise_floor_dbfs, "snr_db": c.snr_db} for c in self.candidates]}
        if extra: result.update(extra)
        return result

STATE = RadioState()

class Handler(BaseHTTPRequestHandler):
    def _json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status": self._json(STATE.snapshot()); return
        if path == "/api/channels": self._json({"channels": STATE.channel_payload()}); return
        if path == "/VERSION":
            body = (VERSION + "\n").encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path == "/": path = "/index.html"
        target = (STATIC / path.lstrip("/")).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file(): self._json({"ok": False, "error": "not_found"}, 404); return
        body = target.read_bytes(); content_type = {".html": "text/html", ".css": "text/css", ".js": "application/javascript"}.get(target.suffix, "application/octet-stream")
        self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self) -> None:
        path = urlparse(self.path).path; length = int(self.headers.get("Content-Length", "0"))
        try: payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError: self._json({"ok": False, "error": "invalid_json"}, 400); return
        try:
            if path == "/api/scan": result = STATE.scan()
            elif path == "/api/stop": STATE.stop(); result = STATE.snapshot()
            elif path == "/api/license/activate": result = STATE.activate_license(str(payload.get("license_serial", "")), str(payload.get("email", "")))
            elif path == "/api/tune": result = STATE.tune(int(payload["channel_number"]))
            elif path == "/api/channel-control":
                if payload.get("action") in ("skip", "block", "clear"): result = STATE.control_current(str(payload["action"]))
                elif payload.get("action") == "clear_all": result = STATE.clear_all_controls()
                else: result = STATE.set_control(int(payload["channel_number"]), str(payload["mode"]))
            elif path == "/api/settings": STATE.settings["rf_gain_db"] = max(0.0, min(49.6, float(payload.get("rf_gain_db", STATE.settings["rf_gain_db"])))); STATE._save_settings(); result = STATE.snapshot()
            else: self._json({"ok": False, "error": "not_found"}, 404); return
            self._json(result)
        except (KeyError, TypeError, ValueError) as error: self._json({"ok": False, "error": str(error)}, 400)
    def log_message(self, *_args: object) -> None: pass

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--host", default="0.0.0.0"); parser.add_argument("--port", type=int, default=8089); parser.add_argument("--simulate", action="store_true"); args = parser.parse_args()
    global STATE; STATE = RadioState(simulate=args.simulate); ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()

if __name__ == "__main__": main()
