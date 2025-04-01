#!/usr/bin/bash

set -e

OUTDIR="/var/tmp/tmt"

echo "Partial cleanup in $OUTDIR..."

rm -rf "$OUTDIR/run" || true
rm -rf "$OUTDIR/build" || true

echo "Cleanup done."
