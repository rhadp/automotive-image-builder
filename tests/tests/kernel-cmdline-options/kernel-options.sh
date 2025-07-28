#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

SSH_PORT=2222
SSH_CMD="sshpass -ppassword ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ConnectTimeout=3 -p $SSH_PORT root@localhost"
IMG_NAME="test.img"
EXPECTED_KERNEL_OPTIONS=("panic=1" "quiet" "loglevel=5" "debug")

# Build the image
echo_log "Building AIB image..."
build --target qemu --mode image --export image test-kernel-options.aib.yml "$IMG_NAME"

# Check if image was created
if [ ! -f "$IMG_NAME" ]; then
    echo_fail "Image build failed: $IMG_NAME not found"
    exit 1
fi

# Start the VM using the built AIB image
automotive-image-runner --ssh-port $SSH_PORT --nographics "$IMG_NAME" &
pid_runner=$!
echo_log "VM running at pid: $pid_runner"

# Wait for SSH availability
RETRY=1
MAX_RETRIES=60
WAIT_TIME=3
RESULT=1

while [ $RESULT -ne 0 ]; do
    sleep $WAIT_TIME
    $SSH_CMD true
    RESULT=$?
    RETRY=$(( $RETRY + 1 ))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo_fail "SSH connection failed"
        # Find and kill qemu-kvm explicitly
        VM_PIDS=$(ps aux | grep 'qemu-kvm' | grep 'hostfwd=tcp::[0-9]\+-:22' | awk '{print $2}')
        if [ -n "$VM_PIDS" ]; then
            kill -9 $VM_PIDS
        fi
        exit 1
    fi
done

# Retrieve the VM's /proc/cmdline to check active kernel boot parameters
CMDLINE=$($SSH_CMD 'cat /proc/cmdline')
echo_log "Kernel cmdline inside VM: $CMDLINE"

# Verify that all expected kernel options are present in the VM's boot parameters
missing_opts=()
all_present=true
for opt in "${EXPECTED_KERNEL_OPTIONS[@]}"; do
    echo "$CMDLINE" | grep -q "$opt"
    if [ $? -eq 0 ]; then
        echo_log "Found kernel option: $opt"
    else
        echo_fail "Missing kernel option: $opt"
        missing_opts+=("$opt")
        all_present=false
    fi
done

# Report test result
if $all_present; then
    echo_pass "All kernel options verified successfully (cmdline, loglevel, debug_logging, quiet)"
    success=0
else
    echo_fail "Missing kernel options: ${missing_opts[*]}"
    success=1
fi

# Clean up automotive-image-runner process
if ps -p $pid_runner > /dev/null; then
    kill -9 $pid_runner
    wait $pid_runner 2>/dev/null || true
fi

# Ensure any leftover QEMU processes are cleaned
ps aux | grep 'qemu-kvm' | grep 'hostfwd=tcp::[0-9]\+-:22' | awk '{print $2}' | xargs -r kill -9

exit $success

