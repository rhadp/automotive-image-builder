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

list_tar () {
    tar --list -f $1
}

list_tar_modules () {
    list_tar $1 | grep "usr/lib/modules/.*/kernel/.*.ko" | xargs basename -a | sed s/.ko.*//
}

# Some default options that make builds faster, override if problematic
FAST_OPTIONS="--define sign_kernel_modules=false"

trybuild() {
     $AIB build --cache $OUTDIR/dnf-cache --build-dir $BUILDDIR $FAST_OPTIONS --define reproducible_image=true "$@" > build.log
}

build() {
   if ! trybuild "$@"; then
      echo FAILED to build image
      tail -n 50 build.log
      exit 1
   fi
}

