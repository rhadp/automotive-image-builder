#!/usr/bin/bash

echo_log() {
    echo "INFO: $1"
}

fatal() {
    echo $@ 1>&2; exit 1
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
    test "$1" = "$2" || fatal "$1 != $2"
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
        echo "PASS: $file has correct UID:GID $expected_uid_gid"
    else
        echo "FAIL: $file has UID:GID $actual_uid_gid, expected $expected_uid_gid"
        exit 1
    fi
}

assert_file_has_permission() {
    local file=$1
    local expected_perm=$2
    local actual_perm=$(stat -c "%a" "$file")
    if [[ "$actual_perm" == "$expected_perm" ]]; then
        echo "PASS: $file has correct permissions $expected_perm"
    else
        echo "FAIL: $file permissions are $actual_perm, expected $expected_perm"
        exit 1
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
     $AIB build --cache $OUTDIR/dnf-cache --build-dir $BUILDDIR $FAST_OPTIONS --define reproducible_image=true "$@" > build.log
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

