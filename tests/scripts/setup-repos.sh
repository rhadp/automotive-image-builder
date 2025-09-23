#!/usr/bin/bash

source "$(dirname $BASH_SOURCE)"/setup-lib.sh

# TODO: Remove after aib 1.1.0 is released and AutoSD 10 pipeline running fine
dnf update -y

# Configure a-i-b base repository
add_repo "aib-base-repo" ${AIB_BASE_REPO}

# Configure a-i-b custom repository when specified
echo "CUSTOM_REPO='"${AIB_CUSTOM_REPO}"'"

if [ -n "${AIB_CUSTOM_REPO}" ]; then
    add_repo "aib-custom-repo" ${AIB_CUSTOM_REPO}
fi
