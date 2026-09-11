from pathlib import Path

PRODUCT_NAME = "N0JCG GMRS Scanner"
VERSION = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
REQUIRED_RTL_SERIAL = "00000462"
PRODUCT_ID = "gmrs-scanner"
LICENSE_PREFIX = "N0JCG-GMR-"
TRIAL_SECONDS = 5 * 60
