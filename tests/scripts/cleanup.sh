#!/usr/bin/bash

echo "Partial cleanup in $OUTDIR..."

rm -rf "$OUTDIR/run" || true
sudo rm -rf "$OUTDIR/build" || true
rm -rf "$OUTDIR/dnf-cache" || true

echo "Cleanup done."
