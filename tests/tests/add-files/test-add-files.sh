#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export tar --extend-define tar_paths=['etc/custom-files','usr/lib/qm/rootfs/etc/qm-custom','etc/test-glob','etc/test-glob-preserve-log','etc/test-glob-preserve'] custom-files.aib.yml out.tar
echo_log "Build completed, output: out.tar"

tar xvf out.tar

echo_log "Checking file contents..."
assert_file_has_content etc/custom-files/file1.txt "name: add_files"
assert_file_has_content etc/custom-files/file2.txt "This is the file content"
assert_file_has_content etc/custom-files/file3.txt "Automotive Image Builder"
assert_file_has_content usr/lib/qm/rootfs/etc/qm-custom/file4.txt "This is the qm file content"

echo_log "Checking flattened glob files..."
# Test that files were copied and flattened to /etc/test-glob
assert_file_has_content etc/test-glob/file1.txt "This is test file 1"
assert_file_has_content etc/test-glob/file2.txt "This is test file 2"

echo_log "Checking flattened recursive glob files..."
# Test that files were copied without directory structure
assert_not_has_file etc/test-glob/subdir1/app.log
assert_file_has_content etc/test-glob-preserve-log/app.log "App log from subdir1"
assert_not_has_file etc/test-glob/subdir2/system.log
assert_file_has_content etc/test-glob-preserve-log/system.log "System log from subdir2"

echo_log "Checking path-preserved glob full copy..."
# Test that files were copied with full preserved directory structure
assert_file_has_content etc/test-glob-preserve/file1.txt "This is test file 1"
assert_file_has_content etc/test-glob-preserve/file2.txt "This is test file 2"
assert_file_has_content etc/test-glob-preserve/subdir1/app.log "App log from subdir1"
assert_file_has_content etc/test-glob-preserve/subdir2/system.log "System log from subdir2"

echo_pass "Image contains all required files"

echo_log "Testing invalid custom top-level directory..."
if trybuild --export tar invalid-custom-dir.aib.yml invalid-out.tar 2> error.txt; then
    echo_fail "Build should have failed for custom top-level directory /custom-dir"
    exit 1
else
    echo_pass "Build failed as expected for custom top-level directory"
fi

echo_log "Checking error message content..."
assert_file_has_content error.txt "Path '/custom-dir' is not allowed"

echo_log "Testing invalid root-level file..."
if trybuild --export tar invalid-root-path.aib.yml invalid-out2.tar 2> error2.txt; then
    echo_fail "Build should have failed for file directly in root /"
    exit 1
else
    echo_pass "Build failed as expected for root-level file"
fi

echo_log "Checking error message content..."
assert_file_has_content error2.txt "Path '/test.txt' is not allowed"

echo_pass "Path validation correctly rejects invalid paths"

