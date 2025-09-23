#!/usr/bin/bash -x

source "$(dirname $BASH_SOURCE)"/../../scripts/test-lib.sh

build --export tar --extend-define "tar_paths=['etc','usr/lib']" test-network-dynamic.aib.yml out.tar
tar xf out.tar

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

