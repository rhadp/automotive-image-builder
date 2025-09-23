#!/usr/bin/bash -x

source "$(dirname $BASH_SOURCE)"/../../scripts/test-lib.sh

echo_log "Starting build for auth users and groups test..."
build --export tar --extend-define "tar_paths=['etc/passwd','etc/group','etc/shadow']" test-users-and-groups.aib.yml out.tar
echo_log "Build completed, output: out.tar"
tar xvf out.tar

PASSWD_PATH="./etc/passwd"
GROUP_PATH="./etc/group"
SHADOW_PATH="./etc/shadow"
EXPECTED_HASH='$6$xoLqEUz0cGGJRx01$H3H/bFm0myJPULNMtbSsOFd/2BnHqHkMD92Sfxd.EKM9hXTWSmELG8cf205l6dktomuTcgKGGtGDgtvHVXSWU.'

# Validate presence of /etc/passwd and expected users
assert_has_file "$PASSWD_PATH"
assert_file_has_content "$PASSWD_PATH" "guest:x:2000:2000::/var/guest:/bin/bash"
assert_file_has_content "$PASSWD_PATH" "foo:x:2042:2042::/home/foo:/sbin/nologin"

# Validate presence of /etc/group and expected groups
assert_has_file "$GROUP_PATH"
assert_file_has_content "$GROUP_PATH" "guest:x:2000:"
assert_file_has_content "$GROUP_PATH" "foo:x:2042:"
assert_file_has_content "$GROUP_PATH" "devs:x:2050:guest"

# Validate presence of /etc/shadow and expected password hash entry
assert_has_file "$SHADOW_PATH"
assert_file_has_content "$SHADOW_PATH" "guest:$EXPECTED_HASH"

echo_pass "users and groups validated successfully."

