#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build for container_images and qm.content.container_images test..."
build --export tar --extend-define tar_paths="['usr/share/containers/storage/overlay-images', 'usr/lib/qm/rootfs/usr/share/containers/storage/overlay-images']" test.aib.yml out.tar
echo_log "Build completed, output: out.tar"

tar xvf out.tar > /dev/null

BASE_IMAGE_JSON="./usr/share/containers/storage/overlay-images/images.json"
QM_IMAGE_JSON="./usr/lib/qm/rootfs/usr/share/containers/storage/overlay-images/images.json"

# Check both images.json files exist
assert_has_file "$BASE_IMAGE_JSON"
assert_has_file "$QM_IMAGE_JSON"

# Validate container from base section
assert_file_has_content "$BASE_IMAGE_JSON" "localhost/auto-apps:latest"

# Validate container from QM section
assert_file_has_content "$QM_IMAGE_JSON" "localhost/qm-apps:latest"

echo_pass "Custom container is properly installed in the image"
