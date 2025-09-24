#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export tar --extend-define tar_paths=['usr/sbin','usr/lib/qm/rootfs/usr/sbin'] test-remove-files.aib.yml out.tar
echo_log "Build completed, output: out.tar"
tar xvf out.tar

# Define the extracted content directories for validation
EXTRACTED_DIR="./usr"
QM_EXTRACTED_DIR="./usr/lib/qm/rootfs"

# Files crond and cupsd should be removed by remove_files
echo_log "Checking files in content section..."
assert_not_has_file "$EXTRACTED_DIR/sbin/crond"

echo_log "Checking files in qm.content section..."
assert_not_has_file "$QM_EXTRACTED_DIR/usr/sbin/cupsd"

echo_pass "The remove_files directive correctly removed specified files."
