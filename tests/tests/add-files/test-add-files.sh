#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export tar --extend-define tar_paths=['dir','usr/lib/qm/rootfs/dir','test-glob','test-glob-preserve-log','test-glob-preserve'] custom-files.aib.yml out.tar
echo_log "Build completed, output: out.tar"

tar xvf out.tar

echo_log "Checking file contents..."
assert_file_has_content dir/file1.txt "name: add_files"
assert_file_has_content dir/file2.txt "This is the file content"
assert_file_has_content dir/file3.txt "Automotive image builder"
assert_file_has_content usr/lib/qm/rootfs/dir/file4.txt "This is the qm file content"

echo_log "Checking flattened glob files..."
# Test that files were copied and flattened to /test-glob
assert_file_has_content test-glob/file1.txt "This is test file 1"
assert_file_has_content test-glob/file2.txt "This is test file 2"

echo_log "Checking flattened recursive glob files..."
# Test that files were copied without directory structure
assert_not_has_file test-glob/subdir1/app.log
assert_file_has_content test-glob-preserve-log/app.log "App log from subdir1"
assert_not_has_file test-glob/subdir2/system.log
assert_file_has_content test-glob-preserve-log/system.log "System log from subdir2"

echo_log "Checking path-preserved glob full copy..."
# Test that files were copied with full preserved directory structure
assert_file_has_content test-glob-preserve/file1.txt "This is test file 1"
assert_file_has_content test-glob-preserve/file2.txt "This is test file 2"
assert_file_has_content test-glob-preserve/subdir1/app.log "App log from subdir1"
assert_file_has_content test-glob-preserve/subdir2/system.log "System log from subdir2"

echo_pass "Image contains all required files"

