#!/usr/bin/bash

set -x

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
TESTKEY=$SCRIPT_DIR/testkey_rsa4096.pem

TO_SIGN="$1"
KEY="${2:-$TESTKEY}"


PARTSIZE=$(jq .signed_files[0].partition_size $TO_SIGN/signing_info.json)

avbtool add_hash_footer --image "$TO_SIGN/aboot/aboot.img" \
	--partition_name "boot" --algorithm SHA256_RSA4096 \
	--key "$KEY" --rollback_index 0 \
	--partition_size $PARTSIZE
avbtool make_vbmeta_image --include_descriptors_from_image "$TO_SIGN/aboot/aboot.img" \
	--algorithm SHA256_RSA4096 \
	--key "$KEY" --rollback_index 0 --output "$TO_SIGN/aboot/vbmeta.img"
