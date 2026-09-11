from pathlib import Path

PRODUCT_NAME = "N0JCG GMRS Scanner"
VERSION = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
REQUIRED_RTL_SERIAL = "00000462"
