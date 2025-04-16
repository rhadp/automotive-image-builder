#!/bin/bash

if [ ! -f duffy.session ]; then
echo "Retrieving an AWS instance"
set +x
duffy client \
 request-session \
 pool=metal-ec2-c5n-centos-9s-x86_64,quantity=1 > duffy.session
fi

set -x

ip=$(jq '.session.nodes[].data.provision.public_ipaddress' duffy.session)
ip=$(echo $ip | sed -e 's|"||g')
echo "IP address: $ip"
session_id=$(jq '.session.id' duffy.session)
session_id=$(echo $session_id | sed -e 's|"||g')
echo "Session: $session_id"

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
  plan --name connect

success=$?
echo $success

mkdir -p ../tmt-run
cp -r /var/tmp/tmt/* ../tmt-run/

echo "Closing session: $session_id"
set +x
duffy client \
 retire-session $session_id
[ -f duffy.session ] && rm duffy.session

exit $success
