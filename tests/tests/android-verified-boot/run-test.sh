#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

set -euo pipefail

# Build bootc builder helper if needed
build_bootc_builder --if-needed

echo_log "Helpers built"

#########################################
### Build base bootc image and disk image
#########################################

echo_log "Starting bootc build..."
build_bootc --target abootqemukvm avb.aib.yml localhost/avb:unsigned
echo_log "Build completed, output: localhost/avb:unsigned"

echo_log "AVB Signing bootc image..."
# Generate a throwaway key (no password) and prepare for resealing with it
openssl genpkey -algorithm ed25519 -outform PEM -out private.pem
$AIB bootc-prepare-reseal --key=private.pem localhost/avb:unsigned localhost/avb:prepared

# Extract aboot files to sign
$AIB bootc-extract-for-signing localhost/avb:prepared to-sign

# Sign aboot files
./sign.sh to-sign/

# Inject signed aboot files and reseal
$AIB bootc-inject-signed --reseal-with-key=private.pem localhost/avb:prepared to-sign localhost/avb:signed

echo_pass "Built signed bootc container"

echo_log "Building bootc disk image..."
$AIB bootc-to-disk-image localhost/avb:signed bootc-signed.img
echo_pass "Built signed bootc disk image"

############################################
### Build bootc image that we will update to
############################################

echo_log "Starting bootc build of update..."
build_bootc --target abootqemukvm avb-update.aib.yml localhost/avb-update:unsigned
echo_log "Build completed, output: localhost/avb-update:unsigned"

echo_log "AVB Signing bootc update image..."
# Generate a throwaway key (no password) and prepare for resealing with it
openssl genpkey -algorithm ed25519 -outform PEM -out private2.pem
$AIB bootc-prepare-reseal --key=private2.pem localhost/avb-update:unsigned localhost/avb-update:prepared

# Extract aboot files to sign
$AIB bootc-extract-for-signing localhost/avb-update:prepared to-sign

# Sign aboot files
./sign.sh to-sign/

# Inject signed aboot files and reseal
$AIB bootc-inject-signed --reseal-with-key=private2.pem localhost/avb-update:prepared to-sign localhost/avb-update:signed

# Export file
sudo podman save --format=oci-archive -o update.tar localhost/avb-update:signed

echo_pass "Built signed bootc update container"

################################
### Boot the image and update it
################################

echo_log "Running bootc disk image..."
VM_PID=$(run_vm bootc-signed.img "serial-console.log" --avb --sharedir .)

PASSWORD="password"
LOGIN_TIMEOUT=40
if ! wait_for_vm_up "$LOGIN_TIMEOUT" "$PASSWORD"; then
    stop_vm "$VM_PID"
    exit 1
fi

assert_file_has_content serial-console.log "AVB verification OK for slot a"

# We should not have less installed yet
if run_vm_command "stat /usr/bin/less" ; then
    echo_fail "less unexpectedly installed before update"
    stop_vm "$VM_PID"
    exit 1
fi

echo_pass "Booted signed bootc disk image with AVC enabled"
run_vm_command "rpm-ostree status"

echo_log "bootc switching to update.tar..."
run_vm_command "mount -t virtiofs host /mnt"
run_vm_command "bootc switch --transport oci-archive /mnt/update.tar"
run_vm_command "reboot now"

echo_log "Waiting for reboot..."
# Wait for reboot
if ! wait_for_vm_up "$LOGIN_TIMEOUT" "$PASSWORD"; then
    stop_vm "$VM_PID"
    exit 1
fi

run_vm_command "rpm-ostree status"

# Check that we have the new update with less in
if ! run_vm_command "stat /usr/bin/less" ; then
    echo_fail "less not installed in update"
    stop_vm "$VM_PID"
    exit 1
fi

echo_pass "Booted into updated image"

stop_vm "$VM_PID"
