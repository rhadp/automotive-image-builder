#!/usr/bin/bash

IF_NEEDED="--if-needed"
if [ "$REBUILD_BOOTC_BUILDER" == "yes" ]; then
    # Force the rebuild of bootc builder container
    IF_NEEDED=""
fi

$AIB build-bootc-builder \
    "$IF_NEEDED" \
    --distro "$AIB_DISTRO"
