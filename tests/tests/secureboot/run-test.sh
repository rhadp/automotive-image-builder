#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

set -euo pipefail

echo_log "Building helpers..."
# Build EFI signer helper
sudo podman build signer -t localhost/test-efi-signer

# Build bootc builder helper if needed
build_bootc_builder --if-needed

# Download EFI firmware that is guaranteed to work with the stored enrolled key
curl -L https://gitlab.com/CentOS/automotive/src/automotive-image-builder/-/releases/1.1.3/downloads/OVMF_CODE.secboot.fd -o OVMF_CODE.secboot.fd
curl -L https://gitlab.com/CentOS/automotive/src/automotive-image-builder/-/releases/1.1.3/downloads/OVMF_VARS.secboot.fd -o OVMF_VARS.secboot.fd

echo_log "Helpers built"

#########################################
### Build base bootc image and disk image
#########################################

echo_log "Starting bootc build..."
build_bootc secureboot.aib.yml localhost/secureboot:unsigned
echo_log "Build completed, output: localhost/secureboot:unsigned"

echo_log "EFI Signing bootc image..."
# Generate a throwaway key (no password) and prepare for resealing with it
openssl genpkey -algorithm ed25519 -outform PEM -out private.pem
$AIB bootc-prepare-reseal --key=private.pem localhost/secureboot:unsigned localhost/secureboot:prepared

# Extract EFI files to sign
$AIB bootc-extract-for-signing localhost/secureboot:prepared to-sign

# Sign EFI files
sudo podman run --rm -ti --privileged -v .:/work localhost/test-efi-signer --certificates db.p12 --password-file password to-sign/efi/*

# Inject signed EFI files and reseal
$AIB bootc-inject-signed --reseal-with-key=private.pem localhost/secureboot:prepared to-sign localhost/secureboot:signed

echo_pass "Built signed bootc container"

echo_log "Building bootc disk image..."
$AIB bootc-to-disk-image localhost/secureboot:signed bootc-signed.img
echo_pass "Built signed bootc disk image"

############################################
### Build bootc image that we will update to
############################################

echo_log "Starting bootc build of update..."
build_bootc secureboot-update.aib.yml localhost/secureboot-update:unsigned
echo_log "Build completed, output: localhost/secureboot-update:unsigned"

echo_log "EFI Signing bootc update image..."
# Generate a throwaway key (no password) and prepare for resealing with it
openssl genpkey -algorithm ed25519 -outform PEM -out private2.pem
$AIB bootc-prepare-reseal --key=private2.pem localhost/secureboot-update:unsigned localhost/secureboot-update:prepared

# Extract EFI files to sign
$AIB bootc-extract-for-signing localhost/secureboot-update:prepared to-sign

# Sign EFI files
sudo podman run --rm -ti --privileged -v .:/work localhost/test-efi-signer --certificates db.p12 --password-file password to-sign/efi/*

# Inject signed EFI files and reseal
$AIB bootc-inject-signed --reseal-with-key=private2.pem localhost/secureboot-update:prepared to-sign localhost/secureboot-update:signed

# Export file
sudo podman save --format=oci-archive -o update.tar localhost/secureboot-update:signed

echo_pass "Built signed bootc update container"

################################
### Boot the image and update it
################################

echo_log "Running bootc disk image..."
VM_PID=$(run_vm bootc-signed.img "serial-console.log" --ovmf-dir=. --secureboot-vars=secboot_vars.fd --sharedir .)

PASSWORD="password"
LOGIN_TIMEOUT=40
if ! wait_for_vm_up "$LOGIN_TIMEOUT" "$PASSWORD"; then
    stop_vm "$VM_PID"
    exit 1
fi

assert_file_has_content serial-console.log "UEFI Secure Boot is enabled"

run_vm_command "rpm-ostree status"

# We should not have less installed yet
if run_vm_command "stat /usr/bin/less" ; then
    echo_fail "less unexpectedly installed before update"
    stop_vm "$VM_PID"
    exit 1
fi

echo_pass "Booted signed bootc disk image with Secure Boot enabled"

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
