#!/bin/bash

echo "[systemd] Waiting for system to settle..."

if ! systemctl is-system-running --wait; then
    echo "[systemd] FAIL: System did not reach 'running' state."
    echo "===== List of failed units ====="
    systemctl list-units --state=failed || true
    echo "======= Full system log ========"
    journalctl --boot || true
    exit 1
fi

echo "[systemd] PASS: System is running normally."
