#!/usr/bin/bash -x

source "$(dirname $BASH_SOURCE)"/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export image partition-absolute-size.aib.yml out.img
echo_log "Build completed, output: out.img"

assert_partition_absolute_size out.img var 524288000 10240
assert_partition_absolute_size out.img qm_var 314572800 10240


