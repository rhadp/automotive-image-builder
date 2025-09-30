# Policy Directory

This directory contains automotive-image-builder policy files (`.aibp.yml` extension).

## Usage

```bash
# Use policy by name (searches installed locations)
automotive-image-builder build --policy security --export qcow2 manifest.aib.yml output.qcow2

# Use policy file (searches local first, then installed)
automotive-image-builder build --policy my-policy.aibp.yml --export qcow2 manifest.aib.yml output.qcow2
```

Policy files use YAML format. See the main README.md for complete documentation.