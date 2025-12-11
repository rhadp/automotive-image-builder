#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

TAR_FILE="out.tar"

# Update cleanup function parameters on each test artifact change
trap 'cleanup_path "$TAR_FILE" "etc"' 'EXIT'

echo_log "Starting build for root_ssh_keys test..."
build_bootc \
    --tar \
    --extend-define tar_paths=['etc/ssh/sshd_config','etc/ssh/authorized_keys/root','etc/ssh/sshd_config.d/99-custom-authorized-keys.conf'] \
    authorized-keys.aib.yml \
    "$TAR_FILE"
echo_log "Build completed, output: $TAR_FILE"

echo_log "Extracting $TAR_FILE..."
tar xvf "$TAR_FILE"

KEY_FILE_PATH="./etc/ssh/authorized_keys/root"
SSHD_CONFIG_PATH="./etc/ssh/sshd_config"
SSHD_CONFIG_OVERRIDE="./etc/ssh/sshd_config.d/99-custom-authorized-keys.conf"
EXPECTED_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCy7ExampleKey123456 root@test"
AUTHORIZED_KEYS_LINE="AuthorizedKeysFile /etc/ssh/authorized_keys/%u .ssh/authorized_keys"

# Validate sshd_config settings
assert_has_file "$SSHD_CONFIG_PATH"
assert_file_has_content "$SSHD_CONFIG_PATH" "PermitRootLogin prohibit-password"
assert_file_has_content "$SSHD_CONFIG_PATH" "PasswordAuthentication no"

# Check key file exists and contains the correct key
assert_has_file "$KEY_FILE_PATH"
assert_file_has_content "$KEY_FILE_PATH" "$EXPECTED_KEY"

# Check sshd_config override exists and has the correct AuthorizedKeysFile line
assert_has_file "$SSHD_CONFIG_OVERRIDE"
assert_file_has_content "$SSHD_CONFIG_OVERRIDE" "$AUTHORIZED_KEYS_LINE"

echo_pass "sshd_config, root_ssh_keys and sshd_config override validated successfully."
