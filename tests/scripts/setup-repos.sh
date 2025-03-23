#!/usr/bin/bash


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


# Configure a-i-b base repository
add_repo "aib-base-repo" ${AIB_BASE_REPO}

# Configure a-i-b custom repository when specified
echo "CUSTOM_REPO='"${AIB_CUSTOM_REPO}"'"

if [ -n "${AIB_CUSTOM_REPO}" ]; then
    add_repo "aib-custom-repo" ${AIB_CUSTOM_REPO}
fi
