# Project Context for AI Code Review

## Project Overview

**Purpose:** CLI tool (CentOS Automotive SIG) that simplifies building OS images for automotive/embedded systems by acting as a higher-level abstraction over OSBuild.
**Type:** Manifest authoring tool + build orchestrator
**Domain:** Automotive / Embedded Systems
**Workflow:** User provides declarative YAML manifest (.aib.yml) → AIB generates deterministic OSBuild JSON → OSBuild builds the image
**Key Dependencies:** OSBuild (build engine), Python stdlib, manifest pre-processor (mpp/)
**Image Types:** Immutable OSTree-based (default, FuSa-ready) and traditional package-based

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
- **CI/CD:** GitLab CI - Configuration is in `.gitlab-ci.yml`. The pipeline likely executes test environments defined in `tox.ini` and runs custom scripts from the `ci-scripts` directory.

## Architecture & Code Organization

### Project Organization
```
.
├── .fmf/
├── aib/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── builder_options_test.py
│   │   ├── exceptions_test.py
│   │   ├── manifest_test.py
│   │   ├── ostree_test.py
│   │   ├── runner_test.py
│   │   ├── simple_test.py
│   │   └── utils_test.py
│   ├── __init__.py
│   ├── exceptions.py
│   ├── exports.py
│   ├── main.py
│   ├── ostree.py
│   ├── runner.py
│   ├── simple.py
│   ├── utils.py
│   └── version.py
├── build/
│   └── build-rpm.sh
├── ci-scripts/
│   └── run_tmt_tests.sh
├── distro/
│   ├── autosd.ipp.yml -> autosd10.ipp.yml
│   ├── autosd10-latest-sig.ipp.yml
│   ├── autosd10-sig.ipp.yml
│   ├── autosd10.ipp.yml
│   ├── autosd9-latest-sig.ipp.yml
│   ├── autosd9-sig.ipp.yml
│   ├── autosd9.ipp.yml
│   ├── cs9.ipp.yml -> autosd9-latest-sig.ipp.yml
│   ├── eln.ipp.yml
│   ├── f40.ipp.yml
│   ├── f40a.ipp.yml
│   ├── f41.ipp.yml
│   ├── rhivos.ipp.yml -> rhivos2.ipp.yml
│   ├── rhivos1.ipp.yml
│   └── rhivos2.ipp.yml
├── docs/
├── examples/
│   ├── complex.aib.yml
│   ├── container.aib.yml
│   ├── lowlevel.mpp.yml
│   ├── qm.aib.yml
│   └── simple.aib.yml
├── files/
│   ├── manifest_schema.yml
│   └── simple.mpp.yml
├── include/
│   ├── arch-aarch64.ipp.yml
│   ├── arch-x86_64.ipp.yml
│   ├── build.ipp.yml
│   ├── computed-vars.ipp.yml
│   ├── content.ipp.yml
│   ├── data.ipp.yml
│   ├── defaults-computed.ipp.yml
│   ├── defaults.ipp.yml
│   ├── empty.ipp.yml
│   ├── image.ipp.yml
│   ├── main.ipp.yml
│   ├── mode-image.ipp.yml
│   ├── mode-package.ipp.yml
│   └── qm.ipp.yml
├── mpp/
│   └── aibosbuild/
│       └── util/
│           ├── __init__.py
│           ├── bls.py
│           ├── checksum.py
│           ├── containers.py
│           ├── ctx.py
│           ├── fscache.py
│           ├── jsoncomm.py
│           ├── linux.py
│           ├── lorax.py
│           ├── lvm2.py
│           ├── mnt.py
│           ├── osrelease.py
│           ├── ostree.py
│           ├── parsing.py
│           └── path.py
├── targets/
│   ├── _abootqemu.ipp.yml
│   ├── _abootqemukvm.ipp.yml
│   ├── _ridesx4_r3.ipp.yml
│   ├── _ridesx4_scmi.ipp.yml
│   ├── abootqemu.ipp.yml
│   ├── abootqemukvm.ipp.yml
│   ├── am62sk.ipp.yml
│   ├── am69sk.ipp.yml
│   ├── aws.ipp.yml
│   ├── beagleplay.ipp.yml
│   ├── ccimx93dvk.ipp.yml
│   ├── j784s4evm.ipp.yml
│   ├── pc.ipp.yml
│   ├── qdrive3.ipp.yml
│   ├── qemu.ipp.yml
│   ├── rcar_s4.ipp.yml
│   ├── rcar_s4_can.ipp.yml
│   ├── ridesx4.ipp.yml
│   ├── ridesx4_r3.ipp.yml
│   ├── ridesx4_scmi.ipp.yml
│   ├── rpi4.ipp.yml
│   ├── s32g_vnp_rdb3.ipp.yml
│   └── tda4vm_sk.ipp.yml
├── tests/
│   ├── plans/
│   │   ├── connect.fmf
│   │   └── local.fmf
│   ├── scripts/
│   │   ├── cleanup.sh
│   │   ├── rebuild-package.sh
│   │   ├── setup-lib.sh
│   │   ├── setup-local.sh
│   │   ├── setup-repos.sh
│   │   └── test-lib.sh
│   ├── tests/
│   │   ├── add-files/
│   │   │   ├── custom-files.aib.yml
│   │   │   ├── main.fmf
│   │   │   └── test-add-files.sh
│   │   ├── container-image/
│   │   │   ├── main.fmf
│   │   │   ├── test-container-image.sh
│   │   │   └── test.aib.yml
│   │   ├── denylist-modules/
│   │   │   ├── main.fmf
│   │   │   ├── test-denylist-modules.sh
│   │   │   └── test.aib.yml
│   │   ├── denylist-rpms/
│   │   │   ├── main.fmf
│   │   │   ├── test-denylist-rpms.sh
│   │   │   └── test.aib.yml
│   │   ├── install-rpms/
│   │   │   ├── main.fmf
│   │   │   ├── test-install-rpms.sh
│   │   │   └── test.aib.yml
│   │   └── main.fmf
│   ├── README.md
│   ├── run_aws.sh
│   ├── test-compose.json
│   └── test.mpp.yml
├── .gitignore
├── .gitlab-ci.yml
├── Containerfile
├── README.md
└── tox.ini
```

### Architecture Patterns
**Code Organization:** Configuration-Driven Command-Line Interface (CLI). The application logic is organized into distinct Python modules within the `aib` package, each handling a specific domain (e.g., `ostree`, `vm`, `runner`). The core workflow is driven by merging and processing declarative YAML configuration files.
**Key Components:**
- `aib.main`: The main entry point. It handles command-line argument parsing, discovers configuration files (`.ipp.yml`), and orchestrates the build process.
- `aib.runner`: The core execution engine. It takes the processed configuration and likely invokes underlying build tools like `osbuild`.
- `aib.simple.ManifestLoader`: Responsible for loading, parsing, and processing the primary user-provided YAML manifest files.
- `aib.ostree`, `aib.exports`: Specialized modules that handle specific functionalities like OSTree repository operations, VM management, and exporting build artifacts.
**Entry Points:** The application is executed via the command line through `aib/main.py`. The primary flow involves parsing arguments, loading and merging a hierarchy of YAML files (`.ipp.yml`, `.aib.yml`), and passing the resulting configuration to the `Runner` to execute the build.

### Important Files for Review Context
- **`aib/main.py`** - As the primary entry point, it defines the CLI arguments and orchestrates the interaction between all other modules. Understanding this file is key to understanding the application's overall workflow.
- **`aib/runner.py`** - This module contains the central build logic. Changes here directly impact how OS images are constructed, making it a critical file for most reviews.
- **`files/manifest_schema.yml`** - This file (inferred from its name and project structure) likely defines the valid structure and options for the input `.aib.yml` manifests. Reviewers need to be aware of this schema to validate changes related to build configuration.

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
- Uses: CentOS Stream 9 image (TODO comment: migrate to CS10)
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
- **OSTree vs Package Mode**: "image" mode creates immutable OSTree-based systems for production; "package" mode creates traditional DNF-managed systems for development.
- **Automotive Terminology**: QM (Quality Managed) partitions for safety-critical code isolation; FuSa (Functional Safety) compliance; bootc containers for atomic updates.
- **Target Hardware**: Extensive automotive SoC support (TI AM62/69, Renesas R-Car, NXP S32G, Qualcomm) with target-specific configurations in `targets/` directory.
- **Container Images**: `quay.io/centos-sig-automotive/automotive-image-builder` for containerized builds; supports both rootless (`--user-container`) and privileged execution.

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
