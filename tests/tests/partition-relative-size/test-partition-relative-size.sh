#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export image partition-relative-size.aib.yml out.img
echo_log "Build completed, output: out.img"

assert_partition_relative_size out.img var 0.2
assert_partition_relative_size out.img qm_var 0.1


