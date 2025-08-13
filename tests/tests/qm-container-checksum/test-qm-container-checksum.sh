#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

SSH_PORT=2222
IMG_NAME="test.img"
PASSWORD="password"
RETRY=1
MAX_RETRIES=60
WAIT_TIME=3
success=0

# Build image
echo_log "Building AIB image..."
build --target qemu --mode image --export image test.aib.yml "$IMG_NAME"

# Verify image exists
assert_image_exists "$IMG_NAME"

# Run VM
VM_PID=$(run_vm "$IMG_NAME" "$SSH_PORT")

# Wait for SSH to be up
if ! wait_for_vm_up "$RETRY" "$MAX_RETRIES" "$WAIT_TIME" "$SSH_PORT" "$PASSWORD"; then
    stop_vm "$VM_PID"
    stop_all_qemus
    exit 1
fi

# Check the status of auto-boot-check
CHECK_OUTPUT=$(run_vm_command "systemctl is-active auto-boot-check || true" "$SSH_PORT" "$PASSWORD")
echo_log "auto-boot-check status: $CHECK_OUTPUT"

if [[ "$CHECK_OUTPUT" == "active" ]]; then
    echo_pass "auto-boot-check is active"
    success=0
else
    echo_fail "auto-boot-check is NOT active"
    echo_log "journalctl -xeu auto-boot-check"
    run_vm_command "journalctl -xeu auto-boot-check -n 500 --no-pager" "$SSH_PORT" "$PASSWORD"
    success=1
fi

# Cleanup
stop_vm "$VM_PID"

exit $success
