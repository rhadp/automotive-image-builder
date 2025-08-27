#!/bin/bash

source $(dirname $BASH_SOURCE)/aws-lib.sh

AIB_DISTRO=${1:-autosd9-sig}
# Base repository for AIB packages needs to be aligned with requested distro
if [[ "${AIB_DISTRO}" == *"autosd9"* ]]; then
    AIB_BASE_REPO="https://autosd.sig.centos.org/AutoSD-9/nightly/repos/AutoSD/compose/AutoSD/\$arch/os/"
    CS_VERSION=9
else
    AIB_BASE_REPO="https://autosd.sig.centos.org/AutoSD-10/nightly/repos/AutoSD/compose/AutoSD/\$arch/os/"
    CS_VERSION=10
fi

export SESSION_FILE="$PWD/duffy.session"

if [ ! -f "$SESSION_FILE" ]; then
    echo "Retrieving an AWS host ..."
    get_aws_session "metal-ec2-c5n-centos-${CS_VERSION}s-x86_64" "$SESSION_FILE"
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

# Release AWS session on exit
trap "release_aws_session $SESSION_FILE" EXIT

ip=$(get_ip_from_session $SESSION_FILE)
echo "IP address: $ip"

# Copy SRPM from previous job artifacts into remote host
# Assuming the CI job passed it as an artifact
SRC_RPM=$(find .. -name '*.src.rpm' | head -n 1)

if [ -z "$SRC_RPM" ]; then
  echo "SRPM not found! Exiting."
  exit 1
fi

echo "Found SRPM: $SRC_RPM"

# Create target directory for SRPM files on the AWS machine
ssh -o StrictHostKeyChecking=no -i $PWD/automotive_sig.ssh root@$ip <<EOF
  mkdir -p /var/tmp/aib-srpm
EOF

# Copy the SRPM to the remote AWS instance (provisioned with Duffy)
scp -o StrictHostKeyChecking=no -i $PWD/automotive_sig.ssh *.src.rpm root@$ip:/var/tmp/aib-srpm/

cd tests && tmt run -v \
  -eNODE=$ip \
  -eNODE_SSH_KEY=$PWD/../automotive_sig.ssh \
  -eBUILD_AIB_RPM=yes \
  -eAIB_DISTRO=$AIB_DISTRO \
  -eAIB_BASE_REPO=$AIB_BASE_REPO \
  plan --name connect

success=$?

mkdir -p ../tmt-run
cp -r /var/tmp/tmt/* ../tmt-run/

exit $success
