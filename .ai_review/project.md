# Project Context for AI Code Review

## Project Overview

**Purpose:** CLI tool (CentOS Automotive SIG) that simplifies building OS images for automotive/embedded systems by acting as a higher-level abstraction over OSBuild.
**Type:** Manifest authoring tool + build orchestrator
**Domain:** Automotive / Embedded Systems
**Workflow:** User provides declarative YAML manifest (.aib.yml) → AIB generates deterministic OSBuild JSON → OSBuild builds the image
**Key Dependencies:** OSBuild (build engine), Python stdlib, manifest pre-processor (mpp/)

The project provides three command-line tools:
- **`aib`** (alias `automotive-image-builder`): Modern bootc-based image builds for production
- **`aib-dev`** (alias `automotive-image-builder-dev`): Traditional package-based builds for development
- **`air`** (alias `automotive-image-runner`): Wrapper of qemu to run virtual machines

**Image Types:**
- Immutable OSTree-based bootc containers (via `aib`, default for production, FuSa-ready)
- Traditional package-based mutable filesystems (via `aib-dev`, for development/iteration)

## Technology Stack

### Core Technologies
- **Primary Language:** Python
- **Framework/Runtime:** No specific framework detected; likely a standalone Python application or library.
- **Architecture Pattern:** Modular, component-based structure suggested by source directories (`aib`, `mpp`, `targets`).

### Key Dependencies (for Context7 & API Understanding)
- **None detected** - The provided dependency list is empty.

### Development Tools & CI/CD
- **Testing:** Test automation is managed via `tox` (inferred from `tox.ini`). A dedicated `tests` directory exists.
- **Code Quality:** No specific tools listed, but configurations are likely present in `tox.ini`.
- **Build/Package:** Build and packaging processes are likely automated with `tox`.
- **CI/CD:** GitLab CI - The pipeline executes test environments defined in `.gitlab-ci.yml` and runs custom scripts from the `ci-scripts` directory.

## Architecture & Code Organization

### Project Organization
```
.
├── aib
│   ├── arguments.py
│   ├── exceptions.py
│   ├── exports.py
│   ├── globals.py
│   ├── __init__.py
│   ├── list_ops.py
│   ├── main_dev.py
│   ├── main.py
│   ├── osbuild.py
│   ├── ostree.py
│   ├── podman.py
│   ├── policy.py
│   ├── progress.py
│   ├── runner.py
│   ├── simple.py
│   ├── tests
│   │   ├── argparse_test.py
│   │   ├── builder_options_test.py
│   │   ├── exceptions_test.py
│   │   ├── exports_test.py
│   │   ├── __init__.py
│   │   ├── manifest_test.py
│   │   ├── ostree_test.py
│   │   ├── policy_test.py
│   │   ├── progress_test.py
│   │   ├── runner_test.py
│   │   ├── simple_test.py
│   │   ├── utils_test.py
│   │   └── version_test.py
│   ├── utils.py
│   └── version.py
├── auto-image-builder.sh
├── automotive-image-builder
├── automotive-image-builder-dev
├── automotive-image-builder.spec.in
├── bin
│   ├── aib
│   ├── aib-dev
│   ├── aib-dev.installed
│   ├── aib.installed
│   ├── air
│   ├── automotive-image-builder -> aib
│   └── automotive-image-builder-dev -> aib-dev
├── build
│   ├── build-rpm.sh
│   └── ociarch
├── ci-scripts
│   ├── aws-lib.sh
│   ├── parallel-test-runner.sh
│   ├── run-shellcheck.sh
│   └── run_tmt_tests.sh
├── Containerfile
├── contrib
│   ├── avb
│   │   ├── sign.sh
│   │   └── testkey_rsa4096.pem
│   └── secure-boot
│       ├── enroll.aib.yml
│       ├── enroll-keys.sh
│       ├── generate-sb-keys.sh
│       ├── pregenerated
│       │   ├── db.auth
│       │   ├── db.p12
│       │   ├── KEK.auth
│       │   ├── password
│       │   ├── PK.auth
│       │   └── secboot_vars.fd
│       ├── README.md
│       └── signer
│           ├── Containerfile
│           └── sign-files.sh
├── distro
│   ├── autosd10.ipp.yml
│   ├── autosd10-latest-sig.ipp.yml
│   ├── autosd10-sig.ipp.yml
│   ├── autosd9.ipp.yml
│   ├── autosd9-latest-sig.ipp.yml
│   ├── autosd9-sig.ipp.yml
│   ├── autosd.ipp.yml -> autosd10.ipp.yml
│   ├── cs9.ipp.yml -> autosd9-latest-sig.ipp.yml
│   ├── eln.ipp.yml
│   ├── f40.ipp.yml
│   ├── f41.ipp.yml
│   ├── rhivos1.ipp.yml
│   ├── rhivos2.ipp.yml
│   └── rhivos.ipp.yml -> rhivos2.ipp.yml
├── docs
│   └── index.html
├── examples
│   ├── complex.aib.yml
│   ├── container.aib.yml
│   ├── glob-files.aib.yml
│   ├── lowlevel.mpp.yml
│   ├── qm.aib.yml
│   ├── radio.container
│   └── simple.aib.yml
├── files
│   ├── bootc-builder.aib.yml
│   ├── emergency.service
│   ├── manifest_schema.yml
│   ├── policies
│   │   ├── hardened.aibp.yml
│   │   └── README.md
│   ├── policy_schema.yml
│   ├── rcu-normal.service
│   ├── rescue.service
│   └── simple.mpp.yml
├── include
│   ├── arch-aarch64.ipp.yml
│   ├── arch-x86_64.ipp.yml
│   ├── build.ipp.yml
│   ├── computed-vars.ipp.yml
│   ├── content.ipp.yml
│   ├── data.ipp.yml
│   ├── defaults-computed.ipp.yml
│   ├── defaults.ipp.yml
│   ├── empty.ipp.yml
│   ├── image.ipp.yml
│   ├── main.ipp.yml
│   ├── mode-image.ipp.yml
│   ├── mode-package.ipp.yml
│   └── qm.ipp.yml
├── LICENSE
├── Makefile
├── mpp
│   ├── aibosbuild
│   │   └── util
│   │       ├── bls.py
│   │       ├── checksum.py
│   │       ├── containers.py
│   │       ├── ctx.py
│   │       ├── fscache.py
│   │       ├── __init__.py
│   │       ├── jsoncomm.py
│   │       ├── linux.py
│   │       ├── lorax.py
│   │       ├── lvm2.py
│   │       ├── mnt.py
│   │       ├── osrelease.py
│   │       ├── ostree.py
│   │       ├── parsing.py
│   │       ├── path.py
│   │       ├── pe32p.py
│   │       ├── rhsm.py
│   │       ├── rmrf.py
│   │       ├── runners.py
│   │       ├── selinux.py
│   │       ├── term.py
│   │       ├── types.py
│   │       └── udev.py
│   └── aib-osbuild-mpp
├── README.maintainer.md
├── README.md
├── systemctl-status.exp
├── targets
│   ├── abootqemu.ipp.yml
│   ├── abootqemukvm.ipp.yml
│   ├── acrn.ipp.yml
│   ├── am62sk.ipp.yml
│   ├── am69sk.ipp.yml
│   ├── aws.ipp.yml
│   ├── azure.ipp.yml
│   ├── beagleplay.ipp.yml
│   ├── ccimx93dvk.ipp.yml
│   ├── ebbr.ipp.yml
│   ├── imx8qxp_mek.ipp.yml
│   ├── include
│   │   ├── _abootqemu.ipp.yml
│   │   ├── _abootqemukvm.ipp.yml
│   │   ├── k3.ipp.yml
│   │   ├── _ridesx4_common.ipp.yml
│   │   ├── _ridesx4.ipp.yml
│   │   └── _ridesx4_scmi.ipp.yml
│   ├── j784s4evm.ipp.yml
│   ├── pc.ipp.yml
│   ├── qdrive3.ipp.yml
│   ├── qemu.ipp.yml
│   ├── rcar_s4_can.ipp.yml
│   ├── rcar_s4.ipp.yml
│   ├── ridesx4.ipp.yml
│   ├── ridesx4_r3.ipp.yml
│   ├── ridesx4_scmi.ipp.yml
│   ├── ridesx4_scmi_r3.ipp.yml
│   ├── rpi4.ipp.yml
│   ├── s32g_vnp_rdb3.ipp.yml
│   └── tda4vm_sk.ipp.yml
├── tests
│   ├── image-tests
│   │   ├── dmesg_clean.sh
│   │   ├── README.md
│   │   ├── rpmdb_initialized.sh
│   │   ├── run-all.sh
│   │   ├── selinux_check.sh
│   │   ├── systemd_running.sh
│   │   └── test-runner.service
│   ├── plans
│   │   ├── connect.fmf
│   │   └── local.fmf
│   ├── README.md
│   ├── run_aws.sh
│   ├── scripts
│   │   ├── cleanup.sh
│   │   ├── init-bootc-builder.sh
│   │   ├── init-build-cache.sh
│   │   ├── login.exp
│   │   ├── rebuild-package.sh
│   │   ├── runcmd.exp
│   │   ├── setup-lib.sh
│   │   ├── setup-local.sh
│   │   ├── setup-repos.sh
│   │   └── test-lib.sh
│   ├── test.mpp.yml
│   └── tests
│       ├── android-verified-boot
│       │   ├── avb.aib.yml
│       │   ├── avb-update.aib.yml
│       │   ├── main.fmf
│       │   ├── password
│       │   ├── run-test.sh
│       │   ├── sign.sh
│       │   └── testkey_rsa4096.pem
│       ├── auth-root-password
│       │   ├── main.fmf
│       │   ├── root-password.aib.yml
│       │   └── run-test.sh
│       ├── auth-root-ssh-keys
│       │   ├── authorized-keys.aib.yml
│       │   ├── main.fmf
│       │   └── run-test.sh
│       ├── auth-users-and-groups
│       │   ├── main.fmf
│       │   ├── run-test.sh
│       │   └── users-and-groups.aib.yml
│       ├── compliance-policy
│       │   ├── compliance.aibp.yml
│       │   ├── containers-storage.aib.yml
│       │   ├── experimental.aib.yml
│       │   ├── lowlevel.mpp.yml
│       │   ├── main.fmf
│       │   ├── minimal.aibp.yml
│       │   ├── run-test.sh
│       │   └── simple-rpms.aib.yml
│       ├── container-image
│       │   ├── container-image.aib.yml
│       │   ├── main.fmf
│       │   └── run-test.sh
│       ├── custom-kernel
│       │   ├── custom-kernel.aib.yml
│       │   ├── main.fmf
│       │   └── run-test.sh
│       ├── denylist-modules
│       │   ├── denylist-modules.aib.yml
│       │   ├── main.fmf
│       │   └── run-test.sh
│       ├── image-size
│       │   ├── image-size-2500mb.aib.yml
│       │   ├── image-size-2gib.aib.yml
│       │   ├── main.fmf
│       │   └── run-test.sh
│       ├── install-rpms
│       │   ├── install-rpms.aib.yml
│       │   ├── main.fmf
│       │   └── run-test.sh
│       ├── kernel-cmdline-options
│       │   ├── kernel-cmdline-options.aib.yml
│       │   ├── main.fmf
│       │   └── run-test.sh
│       ├── main.fmf
│       ├── manage-files
│       │   ├── custom-files.aib.yml
│       │   ├── invalid-custom-dir.aib.yml
│       │   ├── invalid-root-path.aib.yml
│       │   ├── main.fmf
│       │   ├── run-test.sh
│       │   └── test-data
│       │       ├── file1.txt
│       │       ├── file2.txt
│       │       ├── root_fs
│       │       │   └── usr
│       │       │       └── share
│       │       │           └── containers
│       │       │               └── systemd
│       │       │                   └── test.container
│       │       ├── subdir1
│       │       │   └── app.log
│       │       └── subdir2
│       │           └── system.log
│       ├── memory-limit-cpu-weight
│       │   ├── main.fmf
│       │   ├── memory-limit-cpu-weight.aib.yml
│       │   └── run-test.sh
│       ├── minimal-image-boot
│       │   ├── main.fmf
│       │   ├── minimal-image-boot.aib.yml
│       │   └── run-test.sh
│       ├── network-dynamic
│       │   ├── main.fmf
│       │   ├── network-dynamic.aib.yml
│       │   └── run-test.sh
│       ├── network-static
│       │   ├── main.fmf
│       │   ├── network-static.aib.yml
│       │   └── run-test.sh
│       ├── partition-absolute-size
│       │   ├── main.fmf
│       │   ├── partition-absolute-size.aib.yml
│       │   └── run-test.sh
│       ├── partition-relative-size
│       │   ├── main.fmf
│       │   ├── partition-relative-size.aib.yml
│       │   └── run-test.sh
│       ├── qm-container-checksum
│       │   ├── main.fmf
│       │   ├── qm-container-checksum.aib.yml
│       │   ├── qm-container-checksum-policy.aibp.yml
│       │   └── run-test.sh
│       ├── secureboot
│       │   ├── db.p12
│       │   ├── main.fmf
│       │   ├── password
│       │   ├── run-test.sh
│       │   ├── secboot_vars.fd
│       │   ├── secureboot.aib.yml
│       │   ├── secureboot-update.aib.yml
│       │   └── signer
│       │       ├── Containerfile
│       │       └── sign-files.sh
│       ├── selinux-config
│       │   ├── main.fmf
│       │   ├── run-test.sh
│       │   └── selinux-config.aib.yml
│       └── systemd-services
│           ├── main.fmf
│           ├── run-test.sh
│           └── systemd-services.aib.yml
└── tox.ini
```

### Architecture Patterns
**Code Organization:** Configuration-Driven Command-Line Interface (CLI). The application logic is organized into distinct Python modules within the `aib` package, each handling a specific domain (e.g., `ostree`, `runner`, `podman`, `exports`). The core workflow is driven by merging and processing declarative YAML configuration files.
**Key Components:**
- `aib.main`: Entry point for `aib` (bootc-focused builds). Handles command-line argument parsing for bootc container operations and orchestrates bootc-specific workflows.
- `aib.main_dev`: Entry point for `aib-dev` (package-based builds). Handles traditional package-based builds and includes deprecated backwards compatibility commands.
- `aib.list_ops`: Shared list subcommands between `aib` and `aib-dev` for discovering available distros, targets, and exports.
- `aib.runner`: A sudo/container execution engine. It takes the processed configuration and invokes underlying build tools like `osbuild`.
- `aib.simple.ManifestLoader`: Responsible for loading, parsing, and processing the primary user-provided YAML manifest files.
- `aib.podman`: Support for running podman and bootc tools for container image operations.
- `aib.progress`: Nice printing of osbuild logs with progress tracking.
- `aib.policy`: Handlers for loading policy files and validating manifest against them for FuSa compliance.
- `aib.osbuild`: Code for invoking osbuild with proper error handling.
- `aib.ostree`: OSTree repository management operations.
- `aib.exports`: Specialized module that handles exporting build artifacts in various formats (qcow2, raw, simg, container, etc.).
- `aib.utils`: Utility functions including sparse file handling, key management, and filesystem operations.
**Entry Points:** The application has two entry points:
- `aib/main.py` for modern bootc-based builds (accessed via `aib` or `automotive-image-builder`)
- `aib/main_dev.py` for traditional package-based builds (accessed via `aib-dev` or `automotive-image-builder-dev`)
The primary flow involves parsing arguments, loading and merging a hierarchy of YAML files (`.ipp.yml`, `.aib.yml`), and passing the resulting configuration to the `Runner` to execute the build.

### Important Files for Review Context
- **`aib/main.py`** - Entry point for `aib` (bootc builds). Defines CLI arguments for bootc container operations including build, to-disk-image, extract-for-signing, inject-signed, reseal, and prepare-reseal commands.
- **`aib/main_dev.py`** - Entry point for `aib-dev` (package builds). Defines CLI arguments for traditional package-based builds and includes the deprecated build-deprecated command for backwards compatibility.
- **`aib/runner.py`** - This module contains the central build logic. Changes here directly impact how OS images are constructed, making it a critical file for most reviews.
- **`aib/podman.py`** - Handles container operations via Podman, including image mounting, running bootc-image-builder, and container lifecycle management.
- **`aib/osbuild.py`** - Invokes osbuild with proper error handling, manifest creation, and progress tracking.
- **`aib/policy.py`** - Loads and validates policy files (`.aibp.yml`) against manifests for FuSa compliance enforcement.
- **`files/manifest_schema.yml`** - Defines the valid structure and options for the input `.aib.yml` manifests. Reviewers need to be aware of this schema to validate changes related to build configuration.
- **`files/policy_schema.yml`** - Defines the structure for policy files used to enforce FuSa and other compliance requirements.

### Development Conventions
- **Naming:** Python source files use snake_case (`runner.py`). Test files are named with a `_test.py` suffix (`runner_test.py`). Configuration files use a `.ipp.yml` or `.aib.yml` suffix to denote their purpose.
- **Module Structure:** The main application is a single Python package (`aib`) with a flat structure where each file represents a specific feature or component. A parallel `aib/tests/` directory contains the corresponding unit tests.
- **Configuration:** The application is heavily configured via YAML files. User-facing manifests (`.aib.yml`) define a specific build, while reusable snippets (`.ipp.yml`) are organized into `distro/`, `targets/`, and `include/` directories to provide a modular configuration system.
- **Testing:** A two-tiered testing strategy is used:
  - Unit tests are located in `aib/tests/`.
  - Integration and end-to-end tests are in the root `tests/` directory, managed by the Test Management Tool (TMT), as indicated by `.fmf` files and associated shell scripts.

## Code Review Focus Areas

- **[File System & OS Interaction]** - Given the heavy use of `os`, `shutil`, and `tempfile`, verify that all file system operations are robust. Check for correct cross-platform path construction (using `os.path.join`), secure temporary file creation and guaranteed cleanup (e.g., `try...finally` blocks), and proper handling of file system-related exceptions like `FileNotFoundError` or `PermissionError`.

- **[Architecture/Pattern Area]** - The project is a modular command-line tool with distinct components (`runner`, `exports`, `ostree`, `utils`). Ensure that new code maintains this separation of concerns. Business logic should not be added to `main.py`; instead, it should be delegated to the appropriate module. Verify that CLI argument parsing in `argparse` is cleanly decoupled from the core implementation logic.

- **[Code Quality Area]** - The project uses custom `exceptions` and `log` modules. Enforce the use of these project-specific conventions. New error conditions should raise specific exceptions from the `exceptions` module rather than generic ones. Ensure logging is used consistently for user feedback, debugging, and error reporting, adhering to the patterns established in the `log` module.

- **[Domain-Specific Area]** - The core domain is OS image building with `osbuild` and `ostree`. Scrutinize any code that generates or modifies `osbuild` manifests (likely from the `.ipp.yml` files). Pay close attention to logic interacting with `ostree` repositories, as errors here can lead to corrupted or incorrect image builds. Changes should be validated against the expected behavior of these underlying tools.

## Library Documentation & Best Practices

*Library documentation not available*

## CI/CD Configuration Guide

### Pipeline Architecture

**Stages:** `pre` (linting) → `test` (builds/tests) → `container` (multi-arch images) → `deploy` (docs/manifests)

**Workflow Rules:** Anti-duplication logic runs on MR events, web triggers, or branch commits (blocks when open MR exists via `$CI_OPEN_MERGE_REQUESTS`).

**Default Image:** `quay.io/centos-sig-automotive/automotive-osbuild` - contains OSBuild, automotive repos, and build tools.

**External Includes:** `redhat/edge/ci-cd/pipe-x/pipelines-as-code` (ref: `gitlab-ci`) provides downstream trigger templates.

### Key Jobs & Dependencies

**`unit-test-job`** - Runs `tox -e test,coverage` with pytest
- Tests in `aib/tests/` for code in `aib/`
- Coverage tracked via regex: `/TOTAL\s+\d+\s+\d+\s+(\d+%)/` → cobertura XML
- Tox environments: `test`, `coverage` (defined in `tox.ini`)

**`compose-test-modified-distro` / `compose-test-modified-target`**
- Dynamic testing via: `git diff --diff-filter=d --name-only ${CI_MERGE_REQUEST_DIFF_BASE_SHA}`
- Distro: `grep ^distro/` pattern + `allow_failure: true` (some combos unsupported)
- Target: `grep -v "^targets/include" | grep "^targets/"` pattern + NO allow_failure

**`integration_tests_10`** - TMT framework (120min timeout)
- Depends on: `packit-srpm-build` artifact (`*.src.rpm`)
- Uses: CentOS Stream 10 image
- Produces: JUnit XML at `tmt-run/**/junit.xml`
- Currently tests: `autosd10-latest-sig` distro (TODO comment: change to autosd10-sig)

**`container-latest`** - Multi-arch builds via matrix
- Parallel: `amd64`, `arm64` using `saas-linux-small-${ARCH}` runners
- Builds: `$IMAGE:$TAG-$ARCH` format, pushes to Quay.io
- Uses: `CONTAINER_REGISTRY_USER`, `CONTAINER_REGISTRY_PASSWORD` variables
- Produces: dotenv artifact with `MANIFEST` variable for next stage

**`trigger-pipeline`** - Downstream AutoSD-10 integration
- Triggers on MR events with file changes: `**/*.py`, `**/*.yml`, core scripts, `files/*`, `tests/*`
- Uses: template from `pipe-x` include + `BUILD_BRANCH: AutoSD-10` variable

### Current Patterns

**Build Caching:** All build jobs use `--build-dir _build` (not persisted as artifact due to size).

**Tox Environments:** CI references `lint`, `yamllint`, `test`, `coverage` from `tox.ini`.

**Schema Validation:** `files/manifest_schema.yml` used by `pages` job for doc generation.

**Test Matrix:** `tests/test-compose.json` defines distro/target test combinations.

**AWS Setup:** YAML anchors `&prepare-aws-setup` and `&prepare-cs-tmt-setup` for collapsed log sections with Duffy credentials.

### Current Limitations

- `integration_tests_10`: Uses CS9 (TODO: CS10 when TMT in EPEL10)
- `build_doc_demos`: Has `allow_failure: true` (AWS infrastructure variability)
- `compose-test-modified-distro`: Has `allow_failure: true` (expected failures for unsupported distro combinations)

---
<!-- MANUAL SECTIONS - DO NOT MODIFY THIS LINE -->
<!-- The sections below will be preserved during updates -->

## Business Logic & Implementation Decisions

- **Two-Phase Build Process**: AIB uses a compose-then-build pattern where `.aib.yml` manifests are first processed into OSBuild JSON, then executed. This separation ensures reproducibility and allows for manifest validation before expensive build operations.
- **Policy-First Architecture**: The policy system (`.aibp.yml`) validates builds early, preventing invalid configurations from proceeding. FuSa compliance is enforced through policies rather than hardcoded logic.
- **Manifest Processing Pipeline**: High-level `.aib.yml` → Simple manifest parser → Low-level `.mpp.yml` → OSBuild MPP preprocessor → OSBuild JSON. Each stage adds specificity while maintaining determinism.
- **Glob Pattern Safety**: File operations support glob patterns with built-in limits (max_files: 1000) to prevent ARG_MAX issues and system overload during bulk operations.

## Domain-Specific Context

- **OSBuild Integration**: Core dependency on OSBuild for actual image construction. AIB acts as a "manifest authoring tool" generating deterministic OSBuild JSON manifests.
- **Tool Selection**:
  - **`aib`**: For production bootc container images and immutable OSTree-based systems. Supports container builds, disk image conversion, secure boot workflows (extract-for-signing, inject-signed, reseal).
  - **`aib-dev`**: For development with traditional package-based mutable filesystems. Supports rapid iteration with DNF-managed systems. Includes deprecated `build-deprecated` command for automotive-image-builder 1.0 compatibility.
- **Bootc vs Package Mode**:
  - **Bootc mode** (via `aib`): Creates immutable OSTree-based container images for production use with atomic updates and rollback capabilities. Output is a container image that can be converted to disk images.
  - **Package mode** (via `aib-dev`): Creates traditional DNF-managed mutable filesystems for development and rapid iteration. Direct disk image output.
- **Automotive Terminology**: QM (Quality Managed) partitions for safety-critical code isolation; FuSa (Functional Safety) compliance; bootc containers for atomic updates; secure boot workflows for production deployments.
- **Target Hardware**: Extensive automotive SoC support (TI AM62/69, Renesas R-Car, NXP S32G, Qualcomm) with target-specific configurations in `targets/` directory.
- **Container Images**: `quay.io/centos-sig-automotive/automotive-image-builder` for containerized builds; supports both rootless (`--user-container`) and privileged execution.
- **Sparse Image Support**: Android sparse image format (simg) for efficient storage with DONT_CARE (holes), FILL (zeros), and RAW (data) chunks. Use `contrib/write_simg.py` for writing to block devices or files.

## Special Cases & Edge Handling

- **Manifest Auto-Detection**: `.aib.yml` files are automatically converted to use `files/simple.mpp.yml` as the low-level manifest, allowing seamless high-level to low-level transitions.
- **Policy Validation Timing**: Policy restrictions are validated early in the build process (before manifest processing) to provide clear error messages and avoid wasted build time.
- **Build Directory Persistence**: `--build-dir` enables caching of OSBuild artifacts and downloaded packages between builds for significant performance improvements.
- **Cross-Architecture Support**: Can compose manifests for any architecture but can only build for native architecture unless using container isolation.

## Additional Context

- **Security Design**: Transient /etc (tmpfs), immutable root filesystem, readonly containers, and no core dump storage by default. SELinux uses custom "automotive" policy for enhanced security.
- **Schema Evolution**: `files/manifest_schema.yml` and `files/policy_schema.yml` define validation rules. Changes to manifest features require schema updates and corresponding parser logic in `aib/simple.py`.
- **Export Format Flexibility**: Supports multiple simultaneous exports (qcow2, container, ostree-commit, bootc, etc.) from single build. Each format handled by specialized logic in `aib/exports.py`.
- **Testing Strategy**: Unit tests in `aib/tests/`, compose-only tests via `make test-compose`, full integration tests using TMT framework in root `tests/` directory.
- **Sparse File Utilities** (in `aib/utils.py`):
  - `extract_part_of_file(src, dst, start, size)`: Extract partition from image, preserving sparse regions using SEEK_DATA/SEEK_HOLE
  - `truncate_partition_size(src, start, size, block_size)`: Detect trailing holes and return optimal partition size
  - `convert_to_simg(src, dst, block_size)`: Convert raw image to Android sparse image format
  - `create_cpio_archive(dest, basedir, files, compression)`: Create compressed CPIO archives with various formats (gzip, xz, zstd, lz4)
- **Sparse Image Writing** (`contrib/write_simg.py`): Standalone tool for writing Android sparse images to block devices or regular files. Supports interactive confirmation, force mode, and optional zero-initialization of DONT_CARE regions.
