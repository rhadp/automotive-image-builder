#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

TAR_FILE="out.tar"

# Update cleanup function parameters on each test artifact change
trap 'cleanup_path "$TAR_FILE" "modules.list"' 'EXIT'

# Function to log test results
echo_final_test_result() {
    if [ "$1" -eq 0 ] && [ "$2" -eq 0 ]; then
        echo_pass "All module checks passed"
    else
        echo_fail "One or more module checks failed"
    fi
}

echo_log "Starting build..."
build --tar \
    --extend-define tar_paths='usr/lib/modules' \
    denylist-modules.aib.yml \
    "$TAR_FILE"
echo_log "Build completed, output: $TAR_FILE"

echo_log "Extracting modules list from $TAR_FILE..."
list_tar_modules "$TAR_FILE" > modules.list

# Checking modules
echo_log "Checking for nfs module..."
assert_file_doesnt_have_content modules.list "^nfs$"
nfs_exit_code=$?

echo_log "Checking for nfsv3 module..."
assert_file_doesnt_have_content modules.list "^nfsv3$"
nfsv3_exit_code=$?

echo_final_test_result $nfs_exit_code $nfsv3_exit_code

