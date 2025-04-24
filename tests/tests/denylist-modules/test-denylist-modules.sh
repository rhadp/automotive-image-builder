#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

# Function to log test results
echo_final_test_result() {
    if [ "$1" -eq 0 ] && [ "$2" -eq 0 ]; then
        echo "PASS: All module checks passed"
    else
        echo "FAIL: One or more module checks failed"
    fi
}

echo_log "Starting build..."
build --export tar --extend-define tar_paths='usr/lib/modules' test.aib.yml out.tar
echo_log "Build completed, output: out.tar"

list_tar_modules out.tar > modules.list

# Checking modules
echo_log "Checking for nfs module..."
assert_file_doesnt_have_content modules.list "^nfs$"
nfs_exit_code=$?

echo_log "Checking for nfsv3 module..."
assert_file_doesnt_have_content modules.list "^nfsv3$"
nfsv3_exit_code=$?

echo_final_test_result $nfs_exit_code $nfsv3_exit_code

