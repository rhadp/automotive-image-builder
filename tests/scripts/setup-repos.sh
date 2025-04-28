#!/usr/bin/bash

source $(dirname $BASH_SOURCE)/setup-lib.sh


# Configure a-i-b base repository
add_repo "aib-base-repo" ${AIB_BASE_REPO}

# Configure a-i-b custom repository when specified
echo "CUSTOM_REPO='"${AIB_CUSTOM_REPO}"'"

if [ -n "${AIB_CUSTOM_REPO}" ]; then
    add_repo "aib-custom-repo" ${AIB_CUSTOM_REPO}
fi
