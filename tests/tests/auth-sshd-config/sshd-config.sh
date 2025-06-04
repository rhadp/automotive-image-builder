#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build for root SSH config test..."
build --export tar --extend-define tar_paths=['etc/ssh/sshd_config'] test-sshd-config.aib.yml out.tar
echo_log "Build completed, output: out.tar"
tar xvf out.tar

SSHD_CONFIG_PATH="./etc/ssh/sshd_config"

# Validate sshd_config settings
assert_has_file "$SSHD_CONFIG_PATH"
assert_file_has_content "$SSHD_CONFIG_PATH" "PermitRootLogin prohibit-password"
assert_file_has_content "$SSHD_CONFIG_PATH" "PasswordAuthentication no"

echo "PASS: sshd_config validated successfully."

