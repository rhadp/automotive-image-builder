#!/usr/bin/bash

#
# Functions which are used during integration tests setup
#


# Creates repository configuration file with specified repository ID and URL
# Usage: add_repo REPO_ID REPO_URL
add_repo() {
    REPO_ID=$1
    REPO_URL=$2

    # TODO: Once switching to CS10 we can create repo file using dnf config-manager
    repo_file="/etc/yum.repos.d/${REPO_ID}.repo"
    echo "[${REPO_ID}]" > ${repo_file}
    echo "name=${REPO_ID}"  >> ${repo_file}
    echo "baseurl=${REPO_URL}"  >> ${repo_file}
    echo "enabled=1"  >> ${repo_file}
    echo "gpgcheck=0"  >> ${repo_file}
}
