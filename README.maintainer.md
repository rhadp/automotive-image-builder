# Automotive Image Builder – Maintainer Documentation

This document describes the process for maintaining Automotive Image Builder, including release creation and synchronization of upstream utility files.

## Release Process

Follow these steps to create a new release:

1. **Determine the version number:**
    - By default, we increment the **patch version** after each release (e.g., `0.7.0` → `0.7.1`).
    - To make a **minor** or **major** release (e.g., `0.8.0` or `1.0.0`), open a Merge Request updating the version in [`version.py`](./aib/version.py).

2. **Create the release in GitLab:**
    - When all the required changes are merged, go to the GitLab project’s "Releases" section and create a new release.
    - Use the version number as the tag name (e.g., `0.7.0`).
    - Include clear and concise release notes summarizing the changes.

3. **Verify the COPR build:**
    - After the GitLab release is created, confirm that a new [COPR build](https://copr.fedorainfracloud.org/coprs/g/centos-automotive-sig/automotive-image-builder/builds/) was triggered by Packit.
    - Ensure the build completes successfully.

4. **Bump the version number**
    - Open a Merge Request, incrementing the **patch version** in [`version.py`](./aib/version.py) (e.g. `0.8.0`->`0.8.1`).

## Updating and Syncing Files

This project uses [git-crossref](https://github.com/aesteve-rh/git-crossref) to synchronize utility files from upstream repositories. The configuration is defined in [`.gitcrossref`](./.gitcrossref).

### Syncing Files

You need to have `git-crossref` installed locally:

```bash
pip install git-crossref
```

To update synchronized files from upstream repositories:

```bash
git-crossref sync
```

This command will fetch the latest versions of files specified in the configuration and apply any defined transformations.

### Updating the Configuration

To modify which files are synchronized or to update upstream versions:

1. Edit the [`.gitcrossref`](./.gitcrossref) file
2. Update the `version` field to point to a specific commit hash or branch
3. Add or remove files in the `files` section as needed
4. Run `git-crossref sync` to apply the changes
