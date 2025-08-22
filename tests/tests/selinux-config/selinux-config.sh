#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

# Define connection and VM parameters
SSH_PORT=2222
IMG_NAME="test.img"
PASSWORD="password"
RETRY=1
MAX_RETRIES=60
WAIT_TIME=3

EXPECTED_SELINUX_BOOLEANS=(
    "selinuxuser_tcp_server=on"
    "httpd_can_network_connect=on"
    "selinuxuser_ping=off"
    "deny_bluetooth=on"
)

# Build the image
echo_log "Building AIB image..."
build --target qemu --mode image --export image test-selinux-config.aib.yml "$IMG_NAME"

# Check if image was created
assert_image_exists "$IMG_NAME"

# Start the VM using the built AIB image
VM_PID=$(run_vm "$IMG_NAME" "$SSH_PORT")

# Wait until SSH becomes available or fail fast
if ! wait_for_vm_up "$RETRY" "$MAX_RETRIES" "$WAIT_TIME" "$SSH_PORT" "$PASSWORD"; then
    stop_vm "$VM_PID"
    stop_all_qemus
    exit 1
fi

# Retrieve the SELinux booleans to check active settings
SEBOOLS=$(run_vm_command "getsebool -a" "$SSH_PORT" "$PASSWORD")
echo_log "SELinux booleans inside VM: $SEBOOLS"

# Verify that all expected SELinux booleans are present and set correctly
missing_opts=()
all_present=true
for opt in "${EXPECTED_SELINUX_BOOLEANS[@]}"; do
    boolean_name="${opt%%=*}"
    expected_value="${opt##*=}"
    actual_value=$(run_vm_command "getsebool $boolean_name" "$SSH_PORT" "$PASSWORD" | awk '{print $3}')
    if [ "$actual_value" == "$expected_value" ]; then
        echo_log "SELinux boolean $boolean_name is set correctly to $actual_value"
    else
        echo_fail "SELinux boolean $boolean_name is not set correctly. Expected: $expected_value, Found: $actual_value"
        missing_opts+=("$boolean_name")
        all_present=false
    fi
done

# Report test result
if $all_present; then
    echo_pass "All SELinux booleans verified successfully"
    success=0
else
    echo_fail "Missing SELinux booleans: ${missing_opts[*]}"
    success=1
fi

# Clean up automotive-image-runner process
stop_vm "$VM_PID"

exit $success

