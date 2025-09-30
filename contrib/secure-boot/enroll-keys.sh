#!/usr/bin/bash

# Run this in the booted vm to enroll the keys into the EFI vars

KEYDIR="${1:-/usr/share/secureboot-keys}"
echo "Enrolling secureboot keys from $KEYDIR"
efi-updatevar -f $KEYDIR/PK.auth PK
efi-updatevar -f $KEYDIR/KEK.auth KEK   # signed by PK
efi-updatevar -f $KEYDIR/db.auth  db    # signed by KEK
