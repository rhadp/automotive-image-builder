#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

TAR_FILE="out.tar"

# Update cleanup function parameters on each test artifact change
trap 'cleanup_path "$TAR_FILE" "etc" "usr"' 'EXIT'

echo_log "Starting build..."
build --export bootc-tar \
    --extend-define "tar_paths=['etc','usr/lib']" \
    network-dynamic.aib.yml \
    "$TAR_FILE"
echo_log "Build completed, output: $TAR_FILE"

echo_log "Extracting $TAR_FILE..."
tar xf "$TAR_FILE"

# 1. Ensure no static network config files exist
assert_not_has_file etc/main.nmstate
assert_not_has_file usr/lib/boot-check.d/nmstate.conf

# 2. Ensure no persistent NetworkManager connection profiles exist
if ls etc/NetworkManager/system-connections/*.nmconnection &>/dev/null; then
  echo_fail "persistent nmconnection found"
  exit 1
fi

# 3. Ensure NetworkManager is enabled at boot
assert_service_enabled NetworkManager.service content

echo_pass "dynamic networking configured correctly (no static profiles, NetworkManager enabled)"

