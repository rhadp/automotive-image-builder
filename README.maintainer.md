# Automotive Image Builder – Maintainer Documentation

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
    - Open a Merge Request, incrementing th **patch version** in [`version.py`](./aib/version.py) (e.g. `0.8.0`->`0.8.1`).