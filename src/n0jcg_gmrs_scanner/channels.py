from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class GmrsChannel:
    number: int
    name: str
    frequency_hz: int
    group: str
    repeater_input_hz: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)

_LOW = [462_562_500, 462_587_500, 462_612_500, 462_637_500, 462_662_500, 462_687_500, 462_712_500, 467_562_500, 467_587_500, 467_612_500, 467_637_500, 467_662_500, 467_687_500, 467_712_500]
_HIGH = [462_550_000, 462_575_000, 462_600_000, 462_625_000, 462_650_000, 462_675_000, 462_700_000, 462_725_000]
GMRS_CHANNELS = tuple([GmrsChannel(i, f"GMRS {i:02d}", f, "shared" if i <= 14 else "gmrs") for i, f in enumerate(_LOW, 1)] + [GmrsChannel(i, f"GMRS {i:02d}", f, "gmrs", f + 5_000_000) for i, f in enumerate(_HIGH, 15)])

def channel_for_number(number: int) -> GmrsChannel:
    for channel in GMRS_CHANNELS:
        if channel.number == int(number): return channel
    raise ValueError("GMRS channel must be between 1 and 22")
