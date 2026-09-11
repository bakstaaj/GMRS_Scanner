#!/bin/sh
set -eu
APP_DIR=/opt/n0jcg-gmrs-scanner
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# rtl-sdr provides rtl_eeprom, rtl_test, rtl_power, rtl_fm, rtl_sdr, and rtl_tcp.
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y rtl-sdr
fi
# The service runs without a login session; grant it access through plugdev.
getent group plugdev >/dev/null 2>&1 || sudo groupadd --system plugdev
sudo useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin gmrs-scanner 2>/dev/null || true
sudo usermod -aG plugdev gmrs-scanner
sudo install -d -o root -g root "$APP_DIR"
sudo cp -a "$SCRIPT_DIR/src" "$SCRIPT_DIR/web" "$SCRIPT_DIR/VERSION" "$SCRIPT_DIR/README.md" "$APP_DIR/"
sudo install -m 0644 "$SCRIPT_DIR/systemd/n0jcg-gmrs-scanner.service" /etc/systemd/system/
if [ -f /lib/udev/rules.d/rtl-sdr.rules ]; then
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=usb
fi
sudo chown -R gmrs-scanner:gmrs-scanner "$APP_DIR"
sudo systemctl daemon-reload
sudo systemctl enable --now n0jcg-gmrs-scanner.service
sudo systemctl --no-pager --full status n0jcg-gmrs-scanner.service
