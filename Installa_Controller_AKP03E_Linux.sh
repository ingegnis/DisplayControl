#!/bin/sh
set -eu
cd "$(dirname "$0")"
echo "CARISMA / SETUP CONTROLLER AKP03E"
python3 -m pip install --user --only-binary=:all: hidapi==0.15.0
printf '\nPer accesso HID senza root:\n  sudo cp 99-carisma-akp03e.rules /etc/udev/rules.d/\n  sudo udevadm control --reload-rules\n  sudo udevadm trigger\nPoi scollega e ricollega il controller.\n'
