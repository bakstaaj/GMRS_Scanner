import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from n0jcg_gmrs_scanner.channels import GMRS_CHANNELS, channel_for_number
from n0jcg_gmrs_scanner.fft_scan import score_channels, simulated_spectrum
from n0jcg_gmrs_scanner.server import RadioState
from n0jcg_gmrs_scanner import LICENSE_PREFIX, PRODUCT_ID, TRIAL_SECONDS

class ProductTests(unittest.TestCase):
    def test_channel_plan_has_22_centers(self):
        self.assertEqual(len(GMRS_CHANNELS), 22)
        self.assertEqual(channel_for_number(16).frequency_hz, 462_575_000)
        self.assertEqual(channel_for_number(16).repeater_input_hz, 467_575_000)
    def test_fft_selects_strongest_candidate(self):
        channels = [c.as_dict() for c in GMRS_CHANNELS]
        candidates = score_channels(simulated_spectrum(channels), channels)
        self.assertEqual(candidates[0].channel["number"], 16)
        self.assertGreaterEqual(candidates[0].snr_db, 6.0)
    def test_controls_remove_channel_from_scan(self):
        state = RadioState(simulate=True); state.set_control(16, "skip")
        self.assertEqual(state.control(16)["mode"], "skip")
        state.set_control(16, "block")
        self.assertNotIn(16, [c["number"] for c in state.available()])
        state.set_control(16, "active")
        self.assertIn(16, [c["number"] for c in state.available()])
    def test_simulated_scan_and_manual_tune(self):
        state = RadioState(simulate=True); self.assertEqual(state.scan()["tuned"]["number"], 16)
        state.tune(22); self.assertTrue(state.snapshot()["manual_tuned"]); self.assertEqual(state.snapshot()["tuned"]["number"], 22)
    def test_license_identity_and_trial_expiry(self):
        self.assertEqual(PRODUCT_ID, "gmrs-scanner")
        self.assertEqual(LICENSE_PREFIX, "N0JCG-GMR-")
        state = RadioState(simulate=True)
        state.settings["trial_started_at"] = time.time() - TRIAL_SECONDS - 1
        result = state.start_scanner()
        self.assertTrue(result["trial_expired"])
        self.assertFalse(result["running"])

if __name__ == "__main__": unittest.main()
