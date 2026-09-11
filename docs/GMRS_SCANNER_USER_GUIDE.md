# N0JCG GMRS Scanner user guide

Use **Scan active channels** to run the FFT survey. The app stops the audio process before calling `rtl_power`, scores each channel window against the measured noise floor, and starts NFM audio on the strongest candidate above the 6 dB SNR gate.

**Tune** selects one channel immediately and holds it in manual mode. Press **Scan active channels** to return to automatic FFT scanning.

**Skip** excludes a channel from the scan plan for five minutes. **Block** excludes it persistently as an operator control. Use Unskip or Unblock to restore it. These controls are receive-side filters; they do not transmit, inhibit, or reprogram a radio.

The initial scan plan covers the 22 shared channel centers. Channels 15–22 also show their associated repeater-input frequency as reference metadata; the receive scanner tunes the 462 MHz repeater output, not the 467 MHz input. The app does not decode CTCSS/DCS tones in this initial release.

Live RF status requires a real FFT result, an intelligible NFM audio stream, an antenna path, and exclusive RTL-SDR ownership. Simulation and software tests do not prove those conditions.
