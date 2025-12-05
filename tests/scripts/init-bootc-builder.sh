#!/usr/bin/bash

source "$(dirname ${BASH_SOURCE[0]})"/test-lib.sh

IF_NEEDED="--if-needed"
if [ "$REBUILD_BOOTC_BUILDER" == "yes" ]; then
    # Force the rebuild of bootc builder container
    IF_NEEDED=""
fi

build_bootc_builder "$IF_NEEDED"
