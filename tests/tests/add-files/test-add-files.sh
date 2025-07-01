#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export tar --extend-define tar_paths=['dir','usr/lib/qm/rootfs/dir'] custom-files.aib.yml out.tar
echo_log "Build completed, output: out.tar"

tar xvf out.tar

echo_log "Checking file contents..."
assert_file_has_content dir/file1.txt "name: add_files"
assert_file_has_content dir/file2.txt "This is the file content"
assert_file_has_content dir/file3.txt "Automotive image builder"
assert_file_has_content usr/lib/qm/rootfs/dir/file4.txt "This is the qm file content"

echo_pass "Image contains all required files"

