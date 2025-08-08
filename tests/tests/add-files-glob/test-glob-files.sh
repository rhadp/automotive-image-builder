#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build with glob patterns..."
build --export tar --extend-define tar_paths=['test-glob','test-glob-preserve-log','test-glob-preserve'] test-glob-files.aib.yml out-glob.tar
echo_log "Build completed, output: out-glob.tar"

tar xvf out-glob.tar

echo_log "Checking flattened glob files..."
# Test that files were copied and flattened to /test-glob
assert_file_has_content test-glob/file1.txt "This is test file 1"
assert_file_has_content test-glob/file2.txt "This is test file 2"

echo_log "Checking flattened recursive glob files..."
# Test that files were copied without directory structure
assert_file_has_content test-glob-preserve-log/app.log "App log from subdir1"
assert_file_has_content test-glob-preserve-log/system.log "System log from subdir2"

echo_log "Checking path-preserved glob full copy..."
# Test that files were copied with full preserved directory structure
assert_file_has_content test-glob-preserve/file1.txt "This is test file 1"
assert_file_has_content test-glob-preserve/file2.txt "This is test file 2"
assert_file_has_content test-glob-preserve/subdir1/app.log "App log from subdir1"
assert_file_has_content test-glob-preserve/subdir2/system.log "System log from subdir2"

echo_pass "Glob pattern file copying works correctly"
