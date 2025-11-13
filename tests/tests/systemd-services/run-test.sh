#!/usr/bin/bash

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export bootc-tar systemd-services.aib.yml out.tar
echo_log "Build completed, output: out.tar"

echo_log "Extracting out.tar..."
tar xvf out.tar > /dev/null

echo_log "Checking symlinks for content section"
assert_service_enabled sshd.service content
assert_service_disabled httpd.service content

echo_log "Checking symlinks for qm section"
assert_service_enabled crond.service qm
assert_service_disabled cups.service qm

echo_pass "systemd services symlink verification completed!"
