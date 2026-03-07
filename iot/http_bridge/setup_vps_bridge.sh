#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/trustseal-http-bridge"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND_BASE_URL="${BRIDGE_BACKEND_BASE_URL:-https://trustseal.onrender.com}"
BRIDGE_PORT="${BRIDGE_PORT:-80}"

sudo mkdir -p "$APP_DIR"
sudo cp device_ingest_bridge.py "$APP_DIR/device_ingest_bridge.py"
sudo cp requirements.txt "$APP_DIR/requirements.txt"
sudo cp device_ingest_bridge.service /etc/systemd/system/device-ingest-bridge.service

cd "$APP_DIR"
sudo "$PYTHON_BIN" -m venv .venv
sudo "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo "$APP_DIR/.venv/bin/pip" install -r requirements.txt

sudo sed -i "s|Environment=BRIDGE_BACKEND_BASE_URL=.*|Environment=BRIDGE_BACKEND_BASE_URL=$BACKEND_BASE_URL|" /etc/systemd/system/device-ingest-bridge.service
sudo sed -i "s|Environment=BRIDGE_PORT=.*|Environment=BRIDGE_PORT=$BRIDGE_PORT|" /etc/systemd/system/device-ingest-bridge.service

sudo systemctl daemon-reload
sudo systemctl enable device-ingest-bridge.service
sudo systemctl restart device-ingest-bridge.service
sudo systemctl status device-ingest-bridge.service --no-pager
