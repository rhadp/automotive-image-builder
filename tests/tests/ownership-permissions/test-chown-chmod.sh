#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export bootc-tar --extend-define tar_paths=['etc/test-files','usr/lib/qm/rootfs/etc/test-files'] test.aib.yml out.tar
echo_log "Build completed, output: out.tar"
tar xvf out.tar

# Define extracted file paths (content)
EXTRACTED_DIR="./etc/test-files"
FILE1="$EXTRACTED_DIR/file1.txt"
FILE2="$EXTRACTED_DIR/file2.txt"

# Define extracted file paths (QM)
QM_EXTRACTED_DIR="./usr/lib/qm/rootfs/etc/test-files"
QM_FILE1="$QM_EXTRACTED_DIR/file1.txt"
QM_FILE2="$QM_EXTRACTED_DIR/file2.txt"

# Ensure files were extracted (content)
if [ ! -f "$FILE1" ] || [ ! -f "$FILE2" ]; then
    echo "ERROR: One or both content files do not exist after extraction"
    ls -lR "$EXTRACTED_DIR/"
    exit 1
fi

# Ensure files were extracted (QM)
if [ ! -f "$QM_FILE1" ] || [ ! -f "$QM_FILE2" ]; then
    echo "ERROR: One or both QM files do not exist after extraction"
    ls -lR "$QM_EXTRACTED_DIR/"
    exit 1
fi

# Output file details for debug purposes
echo_log "Listing file info after extraction (content):"
ls -l "$FILE1"
ls -l "$FILE2"
stat -c "%u:%g %a" "$FILE1"
stat -c "%u:%g %a" "$FILE2"

echo_log "Checking permissions and ownership (content)..."
# FILE1 - custom permissions and ownership
assert_file_has_permission "$FILE1" "777"
assert_file_has_owner "$FILE1" "65534:65534"
# FILE2 - default permissions and ownership
assert_file_has_permission "$FILE2" "644"
assert_file_has_owner "$FILE2" "0:0"

# Output file details for debug purposes (QM)
echo_log "Listing file info after extraction (QM):"
ls -l "$QM_FILE1"
ls -l "$QM_FILE2"
stat -c "%u:%g %a" "$QM_FILE1"
stat -c "%u:%g %a" "$QM_FILE2"

echo_log "Checking permissions and ownership (QM)..."
# QM_FILE1 - custom permissions and ownership
assert_file_has_permission "$QM_FILE1" "777"
assert_file_has_owner "$QM_FILE1" "65534:65534"
# QM_FILE2 - default permissions and ownership
assert_file_has_permission "$QM_FILE2" "644"
assert_file_has_owner "$QM_FILE2" "0:0"

echo_pass "All file permissions and ownerships are correctly set."
