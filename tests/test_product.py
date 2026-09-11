import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from n0jcg_gmrs_scanner.channels import GMRS_CHANNELS, channel_for_number
from n0jcg_gmrs_scanner.fft_scan import score_channels, simulated_spectrum
from n0jcg_gmrs_scanner.server import RadioState

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

if __name__ == "__main__": unittest.main()
