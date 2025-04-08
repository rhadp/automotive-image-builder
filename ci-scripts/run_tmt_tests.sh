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

cd tests && tmt run -v \
  -eNODE=$ip \
  -eNODE_SSH_KEY=$PWD/../automotive_sig.ssh \
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
