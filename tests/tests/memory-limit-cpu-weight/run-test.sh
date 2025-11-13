#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

# Define expected config path and values
RESOURCE_CONF_PATH="usr/share/containers/systemd/qm.container.d/10-automotive.conf"
EXPECTED_MEMORY_MAX="MemoryMax=100M"
EXPECTED_MEMORY_HIGH="MemoryHigh=80M"
EXPECTED_CPU_WEIGHT="CPUWeight=50"

echo_log "Starting build..."
build --export bootc-tar --extend-define tar_paths="$RESOURCE_CONF_PATH" memory-limit-cpu-weight.aib.yml out.tar
echo_log "Build completed, output: out.tar"

echo_log "Extracting out.tar..."
tar xvf out.tar > /dev/null

assert_has_file "$RESOURCE_CONF_PATH"
assert_file_has_content "$RESOURCE_CONF_PATH" \
  "^$EXPECTED_MEMORY_MAX" \
  "^$EXPECTED_MEMORY_HIGH" \
  "^$EXPECTED_CPU_WEIGHT"

echo_pass "memory_limit and cpu_weight successfully verified in the QM image."
