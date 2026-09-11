# N0JCG GMRS Scanner

Receive-only Raspberry Pi GMRS/FRS channel scanner for an RTL-SDR. It performs a one-shot FFT survey across the 462/467 MHz channel plan, scores active channels, tunes the strongest candidate with NFM audio, and provides skip, block, and manual channel controls.

This is an independent product. It uses RTL-SDR serial `00000462` by default; change the serial in the service or application configuration when assigning a different dongle. Serial identity is preferred over unstable USB indexes.

## Development

```bash
python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m n0jcg_gmrs_scanner.server --simulate --port 8089
```

Open `http://127.0.0.1:8089/`. Simulation is deterministic and validates the control path only; it is not evidence of live RF, audio, antenna coverage, or RTL-SDR ownership.

## Live operation

Live scanning requires `rtl_power`, `rtl_fm`, a suitable 462/467 MHz antenna path, and an RTL-SDR. The app scans the 22 shared GMRS/FRS channel centers, releases `rtl_fm` before each FFT survey, then starts NFM audio on the strongest valid candidate. Manual tuning pauses automatic rescans until Scan is pressed again.

On Debian/Raspberry Pi OS, install the complete RTL-SDR utility set with `sudo apt-get update && sudo apt-get install -y rtl-sdr`. This package supplies `rtl_eeprom`, `rtl_test`, `rtl_power`, `rtl_fm`, `rtl_sdr`, and `rtl_tcp`. Confirm the tools with `command -v rtl_eeprom rtl_test rtl_power rtl_fm rtl_sdr rtl_tcp` before starting the service.

If `rtl_test` reports `usb_open error -3`, run the installer again so it reloads `/lib/udev/rules.d/rtl-sdr.rules` and grants `gmrs-scanner` membership in `plugdev`. Unplug and reconnect the dongle, then verify with `sudo -u gmrs-scanner rtl_test -d 0`.

The channel frequencies follow the FCC-published shared 22-channel plan. This application only receives; it does not transmit or control PTT. Operators remain responsible for lawful radio use.
