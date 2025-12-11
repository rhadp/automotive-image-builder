# Policy Directory

This directory contains automotive-image-builder policy files (`.aibp.yml` extension).

## Usage

```bash
# Use policy by name (searches installed locations)
aib build --policy security manifest.aib.yml output

# Use policy file (searches local first, then installed)
aib build --policy my-policy.aibp.yml manifest.aib.yml output
```

Policy files use YAML format. See the main README.md for complete documentation.
