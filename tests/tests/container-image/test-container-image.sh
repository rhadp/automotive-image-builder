#!/usr/bin/bash -x

export TESTDIR="${TMT_TREE:-$(realpath "$(dirname "$0")/../..")}"
source "$TESTDIR/scripts/test-lib.sh"

echo_log "Starting build..."
build --export tar --extend-define tar_paths='usr/share/containers/storage/overlay-images' test.aib.yml out.tar
echo_log "Build completed, output: out.tar"

tar xvf out.tar

echo_log "Extracting image names from images.json..."
cat usr/share/containers/storage/overlay-images/images.json | jq .[0].names[0] > image_names

echo_log "Checking file content of image_names..."
assert_file_has_content image_names "localhost/auto-apps:latest"
echo_log "Assertion completed for image_names."

echo "PASS: Custom container is properly installed in the image"

