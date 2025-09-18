#!/usr/bin/bash

echo_log() {
    echo "INFO: $1"
}

echo_pass() {
    echo "PASS: $1"
}

echo_fail() {
    echo "FAIL: $1"
}

fatal() {
    echo "FAIL: $@" 1>&2; exit 1
}

_fatal_print_file() {
    file="$1"
    shift
    ls -al "$file" >&2
    sed -e 's/^/# /' < "$file" >&2
    fatal "$@"
}

_fatal_print_files() {
    file1="$1"
    shift
    file2="$1"
    shift
    ls -al "$file1" >&2
    sed -e 's/^/# /' < "$file1" >&2
    ls -al "$file2" >&2
    sed -e 's/^/# /' < "$file2" >&2
    fatal "$@"
}

assert_streq () {
    test "$1" = "$2" || fatal ${3:-"$1 != $2"}
}

assert_str_match () {
    if ! echo "$1" | grep -E -q "$2"; then
        fatal "$1 does not match regexp $2"
    fi
}

assert_not_streq () {
    (! test "$1" = "$2") || fatal "$1 == $2"
}

assert_has_file () {
    test -f "$1" || fatal "Couldn't find '$1'"
}

assert_not_has_file () {
    test ! -f "$1" || fatal "File '$1' shouldn't exist"
}

assert_has_dir () {
    test -d "$1" || fatal "Couldn't find '$1'"
}

assert_file_has_content () {
    fpath=$1
    shift
    for re in "$@"; do
        if ! grep -q -e "$re" "$fpath"; then
            _fatal_print_file "$fpath" "File '$fpath' doesn't match regexp '$re'"
        fi
    done
}

assert_file_doesnt_have_content () {
    fpath=$1
    shift
    for re in "$@"; do
        if grep -q -e "$re" "$fpath"; then
            _fatal_print_file "$fpath" "File '$fpath' unexpectedly matches regexp '$re'"
        fi
    done
}

assert_file_has_owner() {
    local file=$1
    local expected_uid_gid=$2
    local actual_uid_gid=$(stat -c "%u:%g" "$file")
    if [[ "$actual_uid_gid" == "$expected_uid_gid" ]]; then
        echo_pass $file has correct UID:GID $expected_uid_gid"
    else
        echo_fail $file has UID:GID $actual_uid_gid, expected $expected_uid_gid"
    fi
}

assert_file_has_permission() {
    local file=$1
    local expected_perm=$2
    local actual_perm=$(stat -c "%a" "$file")
    if [[ "$actual_perm" == "$expected_perm" ]]; then
        echo_pass $file has correct permissions $expected_perm
    else
        echo_fail $file permissions are $actual_perm, expected $expected_perm
    fi
}

resolve_systemd_wants_path() {
    local service_name="$1"
    local section="$2"

    if [ "$section" = "content" ]; then
        echo "etc/systemd/system/multi-user.target.wants/$service_name"
    elif [ "$section" = "qm" ]; then
        echo "usr/lib/qm/rootfs/etc/systemd/system/multi-user.target.wants/$service_name"
    else
        fatal "Unknown section: $section"
    fi
}

assert_service_enabled() {
    local service_name="$1"
    local section="$2"
    local symlink_path
    symlink_path=$(resolve_systemd_wants_path "$service_name" "$section")

    if test -L "$symlink_path"; then
        echo_pass "$service_name is enabled in $section."
    else
        echo_fail "$service_name is not enabled in $section."
        exit 1
    fi
}

assert_service_disabled() {
    local service_name="$1"
    local section="$2"
    local symlink_path
    symlink_path=$(resolve_systemd_wants_path "$service_name" "$section")

    if test -L "$symlink_path"; then
        echo_fail "$service_name should be disabled in $section but symlink exists!"
        exit 1
    else
        echo_pass "$service_name is disabled in $section."
    fi
}

assert_partition_relative_size() {
    local img=$1
    local label=$2
    local expected_ratio=$3
    local epsilon=${4:-0.01}

    local loop
    loop=$(sudo losetup --find --partscan --show "$img") || fatal "FAIL: Failed to setup loop device"
    trap "sudo losetup -d $loop" RETURN

    local img_size
    img_size=$(stat -c %s "$img") || fatal "FAIL: Failed to stat image file"

    local part=""
    for p in /dev/$(basename "$loop")p*; do
        if sudo blkid "$p" 2>/dev/null | grep -q "LABEL=\"$label\""; then
            part=$p
            break
        fi
    done

    if [ -z "$part" ]; then
        fatal "FAIL: Partition with label '$label' not found in image"
    fi

    local part_size
    part_size=$(sudo blockdev --getsize64 "$part") || fatal "FAIL: Failed to get size of partition $part"

    local ratio
    ratio=$(awk -v ps=$part_size -v is=$img_size 'BEGIN { print ps / is }')

    local lower upper
    lower=$(awk -v er=$expected_ratio -v e=$epsilon 'BEGIN { print er - e }')
    upper=$(awk -v er=$expected_ratio -v e=$epsilon 'BEGIN { print er + e }')

    if awk -v r=$ratio -v lo=$lower -v hi=$upper 'BEGIN { exit !(r >= lo && r <= hi) }'; then
        echo "PASS: Partition '$label' relative size $ratio matches expected $expected_ratio ± $epsilon"
    else
        fatal "FAIL: Partition '$label' relative size $ratio NOT in range [$lower, $upper]"
    fi
}

assert_partition_absolute_size() {
    local img=$1
    local label=$2
    local expected_size=$3
    local epsilon=${4:-0}  # optional tolerance in bytes

    local loop
    loop=$(sudo losetup --find --partscan --show "$img") || fatal "FAIL: Failed to setup loop device"
    trap "sudo losetup -d $loop" RETURN

    local part=""
    for p in /dev/$(basename "$loop")p*; do
        if sudo blkid "$p" 2>/dev/null | grep -q "LABEL=\"$label\""; then
            part=$p
            break
        fi
    done

    if [ -z "$part" ]; then
        fatal "FAIL: Partition with label '$label' not found in image"
    fi

    local part_size
    part_size=$(sudo blockdev --getsize64 "$part") || fatal "FAIL: Failed to get size of partition $part"

    local lower upper
    lower=$(awk -v es=$expected_size -v e=$epsilon 'BEGIN { print es - e }')
    upper=$(awk -v es=$expected_size -v e=$epsilon 'BEGIN { print es + e }')

    if awk -v ps=$part_size -v lo=$lower -v hi=$upper 'BEGIN { exit !(ps >= lo && ps <= hi) }'; then
        echo "PASS: Partition '$label' size $part_size bytes matches expected $expected_size ± $epsilon"
    else
        fatal "FAIL: Partition '$label' size $part_size bytes NOT in range [$lower, $upper]"
    fi
}

list_tar () {
    tar --list -f $1
}

list_tar_modules () {
    list_tar $1 | grep "usr/lib/modules/.*/kernel/.*.ko" | xargs basename -a | sed s/.ko.*//
}

save_to_tmt_test_data () {
    cp $1 "${TMT_TEST_DATA}"
}

# Some default options that make builds faster, override if problematic
FAST_OPTIONS="--define sign_kernel_modules=false"

trybuild() {
    $AIB build \
        --distro=$AIB_DISTRO \
        --cache $OUTDIR/dnf-cache \
        --build-dir $BUILDDIR $FAST_OPTIONS \
        --define reproducible_image=true \
        "$@" > build.log
}

build() {
   if ! trybuild "$@"; then
      echo FAILED to build image
      # only show last 50 lines in
      tail -n 50 build.log
      # save build log to tmt test data
      save_to_tmt_test_data build.log
      exit 1
   fi
   save_to_tmt_test_data build.log
}

# Check if the image was created
assert_image_exists() {
    local image=$1
    if [ ! -f "$image" ]; then
        echo_fail "Image build failed: $image not found"
        exit 1
    fi
}

# Start the VM and return its PID
run_vm() {
    local image=$1
    local log_file=${2:-"serial-console.log"}
    $AIR --virtio-console console.sock --nographics "$image" > "$log_file" 2>&1 &
    local pid=$!
    >&2 echo "INFO: VM running at pid: $pid"
    echo "$pid"
}

# Wait until VM console is available
wait_for_vm_up() {
    local login_timeout=${1:-0}
    local password=${5:-password}
    local result=1

    sleep 2 # Ensure console.sock is created by qemu start
    if $(dirname $BASH_SOURCE)/login.exp console.sock $password $login_timeout 60; then
        return 0;
    else
        echo_fail "Failed to connect to virtual console"
        return 1
    fi
}

# Run a command inside the VM
run_vm_command() {
    local cmd="$1"
    >&2 echo "INFO: Running VM command: $cmd"
    $(dirname $BASH_SOURCE)/runcmd.exp console.sock "$cmd"
}

# Kill the given VM by PID
stop_vm() {
    local pid="$1"
    local log_file=${2:-"serial-console.log"}
    if ps -p "$pid" > /dev/null; then
        /usr/bin/kill --timeout 2000 TERM --timeout 1000 KILL "$pid"
        wait "$pid" 2>/dev/null || true
    fi
    if [ -f "$log_file" ]; then
        # Save serial-console.log into tmt data
        save_to_tmt_test_data "$log_file"
    fi
}

