#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

# Update cleanup function parameters on each test artifact change
trap 'cleanup_path "error.txt" "out.json"' 'EXIT'

echo_log "Starting trybuild with denied RPM..."
if trybuild --export rpmlist --extend-define denylist_rpms=strace denylist-rpms.aib.yml out.json 2> error.txt; then
    echo_log "ERROR: Build should not have succeeded with denied RPM."
    fatal should not have succeeded build with denied rpm
else
    echo_pass "Build failed as expected due to denied RPM."
fi

echo_log "Checking error message content..."
assert_file_has_content error.txt "Rootfs contains denied rpms"
echo_log "Assertion completed for error.txt."

