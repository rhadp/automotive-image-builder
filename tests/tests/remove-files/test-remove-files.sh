#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export tar --extend-define tar_paths=['test-files','usr/lib/qm/rootfs/test-files'] test.aib.yml out.tar
echo_log "Build completed, output: out.tar"
tar xvf out.tar

# Define the extracted content directories for validation
EXTRACTED_DIR="./test-files"
QM_EXTRACTED_DIR="./usr/lib/qm/rootfs/test-files"

# Validate section:
# 'keep.txt' should exist, 'delete.txt' should be removed by remove_filesecho_log "Checking files in content section..."
assert_has_file "$EXTRACTED_DIR/keep.txt"
assert_file_doesnt_exist "$EXTRACTED_DIR/delete.txt"

echo_log "Checking files in qm.content section..."
assert_has_file "$QM_EXTRACTED_DIR/qm_keep.txt"
assert_file_doesnt_exist "$QM_EXTRACTED_DIR/qm_delete.txt"

echo_pass "remove_files directive correctly removed specified files."

