from dataclasses import dataclass
from typing import Iterable

MIN_VALID_SNR_DB = 6.0

@dataclass(frozen=True)
class FftPoint:
    frequency_hz: int
    power_dbfs: float

@dataclass(frozen=True)
class ScanCandidate:
    channel: dict
    peak_frequency_hz: int
    peak_dbfs: float
    noise_floor_dbfs: float
    snr_db: float

def score_channels(points: Iterable[FftPoint], channels: Iterable[dict], half_width_hz: int = 7_500) -> list[ScanCandidate]:
    points = tuple(points)
    if not points: return []
    floor = sorted(point.power_dbfs for point in points)[max(0, len(points) // 10)]
    scored = []
    for channel in channels:
        center = int(channel["frequency_hz"])
        window = [p for p in points if abs(p.frequency_hz - center) <= half_width_hz]
        if window:
            peak = max(window, key=lambda p: p.power_dbfs)
            scored.append(ScanCandidate(channel, peak.frequency_hz, peak.power_dbfs, floor, peak.power_dbfs - floor))
    return sorted(scored, key=lambda item: (item.snr_db, item.peak_dbfs), reverse=True)

def simulated_spectrum(channels: Iterable[dict]) -> list[FftPoint]:
    points = []
    for channel in channels:
        peak = -29.0 if int(channel["number"]) == 16 else -67.0
        for offset in (-6_000, -2_000, 2_000, 6_000):
            points.append(FftPoint(int(channel["frequency_hz"]) + offset, peak if offset == 2_000 else peak - 10))
    return points
