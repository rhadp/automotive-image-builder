#!/usr/bin/bash

if [ -d "$BUILDCACHEDIR" ]; then
    echo "Build cache directory '$BUILDCACHEDIR' already exists, skipping"
    exit 0
fi

MIN_IMAGE_MFT="/tmp/minimal-image.aib.yml"
cat > "$MIN_IMAGE_MFT" << EOF
name: minimal-boot

content:
  rpms: []

qm:
  content:
    rpms: []
EOF

echo "Populating build cache directory '$BUILDCACHEDIR' started"
$AIB download \
    --distro=$AIB_DISTRO \
    --cache $OUTDIR/dnf-cache \
    --build-dir $BUILDCACHEDIR \
    "$MIN_IMAGE_MFT"
