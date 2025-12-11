# Automotive Image Builder

Automotive Image Builder (AIB) is a tool to create various kinds of OS images based on CentOS-derived
distributions. The images can support package-based mode (called "package") as well as image-based mode
(called "image").

The main tool is called `aib`, and its primary function is to compose manifests.
The compose operation takes a YAML-based Automotive Image Builder manifest and a set of options 
that affect the compose, and it resolves the manifest into an osbuild JSON file. This
JSON file contains precise instructions for building an image using the
specific software chosen during the compose, such as package versions and 
container images.

Build a `qcow2` image:

```shell
 $ aib-dev build --distro autosd10 --mode package --target qemu --export qcow2 my-image.aib.yml osbuild.json
```

These commands compose the `osbuild.json` file and then build it and export the `qcow2` output to the the `output` 
directory, for example, `output/qcow2/disk.qcow2`. 

Run the QCOW image in a virtual machine:

```shell
 $ air  output/qcow2/disk.qcow2
```

Note: When you run `aib-dev build`, it's helpful and time-saving
to pass the option `--build-dir some/dir`, which stores intermediate data, such as downloaded
RPMs between runs.

## Installation and dependencies

Automotive Image Builder depends on osbuild extensions for automotive use.

To install Automotive Image Builder, refer to the
[AutoSD documentation](https://sigs.centos.org/automotive/getting-started/proc_installing-automotive-image-builder/)

Alternatively, you can also run Automotive Image Builder from
[a container](https://sigs.centos.org/automotive/getting-started/proc_running-automotive-image-builder-from-container/).

## Manifests

Automotive Image Builder supports two types of image manifests. The
default manifest uses the extension `.aib.yml` and is a high-level,
declarative YAML-based format, for example:
```yaml
name: image-with-vim

content:
  rpms:
    - vim
```


You can find detailed
[schema documentation for the manifest syntax](https://centos.gitlab.io/automotive/src/automotive-image-builder/simple_manifest.html).

You can also experiment with the example manifests in the [examples](examples) directory:

```shell
$ aib-dev build --export qcow2 examples/simple.aib.yml example.qcow2
$ air example.qcow2
```

The sample-images repository
(https://gitlab.com/CentOS/automotive/sample-images) has a larger set
of functional examples.

There is also support for a low-level manifest file format, with extension `.mpp.yml`. This is
a format closer to the osbuild imperative format, and writing such files requires deeper
knowledge of how osbuild works, as well as the internals of Automotive Image Builder. This
is used internally to implement the higher-level manifest format, but it is also available
to the end user. However, we don't recommend using this format, as it is quite difficult to use
and not well documented.

## Controlling the image built

When composing (or building) a manifest, there are some core options that control what gets built:

* `--arch`: The hardware architecture to build for (`x86_64` or `aarch64`). If not specified the native
   architecture is used. Note: It is possible to compose an image for any architecture, but you can
   only build one for the native architecture.

* `--target`: The board to target, defaults to `qemu`. You can get a list of the supported targets from
  `aib list-targets`.

* `--mode`: Either `package` or `image`. Default is `image`. Package mode is a read-write OS that uses
  `dnf` to install packages. Image mode is an immutable OS image based on OSTree, which supports
  atomic updates, but no package-level modifications. Image mode is meant for
  production, while package mode is more useful during development and testing.

* `--distro`: There are a set of distribution definitions that can be used. These define which package
  repositories to use. The default is "autosd10-sig", but the full list can be obtained with
  `aib list-dist`.  It is also possible to extend the list of distributions
  with your custom ones by placing them in a directory called "/some/dir/distro" and passing
  `--include /some/dir` on the command line.

When the manifest has been composed, the generated osbuild JSON file can contain several types of
build artifacts. For example, it can generate both raw image files and `qcow2` files. When
building you need to use the `--export` option to select what you want to build. The available export options
are:

* `image`: A raw disk image with partitions
* `qcow2`: A qcow2-format disk image with partitions
* `ext4`: An ext4 filesystem containing just the rootfs partition (i.e. no boot partitions, etc.)
* `aboot`: An Android boot system partition image and a boot partition
* `container`: A container image you can run with podman or docker
* `tar`: A tar file containing the basic rootfs files
* `ostree-commit`: An OSTree repository with the commit built from the image
* `bootc`: A bootc image
* `rpmlist`: A JSON file listing all the RPMs used in the image

## Policy System

Automotive Image Builder supports a policy system that allows external policy files to enforce build restrictions and configurations. This replaces hard-coded flags with flexible, external policy definitions.

### Using Policies

Use the `--policy` flag to apply a policy file. The policy argument can be:

- **Policy name**: `--policy security` (searches installed locations only)
- **Policy filename**: `--policy my-policy.aibp.yml` (searches local directory first, then installed)
- **Full path**: `--policy /path/to/policy.aibp.yml`

Installed policy locations (searched in order):
1. `/etc/automotive-image-builder/policies/` (system-wide)
2. `/usr/lib/automotive-image-builder/files/policies/` (package-provided)

```shell
$ aib-dev build --policy security --export qcow2 my-image.aib.yml output.qcow2
```

Policy files use the `.aibp.yml` extension and define restrictions and forced configurations:

```yaml
name: security-policy
description: Security hardening policy for production images

restrictions:
  modes:
    allow:
      - image
  
  variables:
    force:
      disable_ipv6: true
      ld_so_cache_protected: true
  
  rpms:
    disallow:
      - dosfstools
      - e2fsprogs
  
  sysctl:
    force:
      "net.core.busy_poll": "0"
      "net.ipv4.conf.all.mc_forwarding": "0"
```

### Policy Features

Policies can enforce:

- **Mode restrictions**: Allow/disallow package vs image mode
- **Target restrictions**: Control which hardware targets are allowed
- **Distribution restrictions**: Limit which distributions can be used
- **Variable enforcement**: Force specific manifest variables
- **Package restrictions**: Block specific RPMs from being installed
- **Kernel module restrictions**: Prevent loading of specific kernel modules
- **Sysctl enforcement**: Set required kernel parameters
- **SELinux boolean enforcement**: Configure SELinux policy settings
- **Manifest validation**: Block specific manifest properties or values

Policy validation happens early in the build process, providing clear error messages when restrictions are violated.

The complete policy file schema is defined in [files/policy_schema.yml](files/policy_schema.yml).

## Manifest variables

The low-level manifest format supports a variety of variables that you can set in the manifest file or
on the command line. In the high-level manifests, these are automatically set based on the options in
the manifest and the target, distro, and mode that you choose. However, it can sometimes be useful to
modify these variables on the command line during development and testing.

To modify these variables on the command line, you can use:

* `--define VAR=VALUE`: Sets the variable to the specified value (YAML format).

* `--define-file PATH`: Loads variables from a YAML dict in a file, where the keys are variable names.

* `--extend-define VAR=VALUE`: Similar to `--define`, but only usable for list-based variables.
  It extends the existing list (or starts a new one if unset). You can specify
  either a list or a single item.

Commonly used supported variables include:

* `use_qm`: If true, includes QM partition support in the image.
* `qm_memory_max`: Sets the maximum memory that can be used by the QM partition (see the `MemoryMax` systemd option).
* `extra_rpms`: Adds extra RPMs to the image (supported by any manifests, e.g., in sample-images).
* `image_size`: Specifies the size (in bytes, as a string) of the generated image.
* `use_composefs_signed`: If false, ostree commits don’t require signing. Useful for modifying ostree images on the target system (e.g., layering packages).
* `use_transient_etc`: If false, changes to `/etc` persist across boots in image-based builds. Not recommended for production but useful for testing.
* `use_static_ip`: If set, disables NetworkManager and applies static network configuration via the following options:
* `static_ip`: The IP address
* `static_gw`: The default gateway
* `static_dns`: The DNS server
* `static_ip_iface`: The network interface name
* `static_ip_modules`: The network driver kernel modules to load (if any)
* `use_debug`: If true, enables detailed debugging output during boot.

## Using QM

Automotive Image Builder supports the [QM](https://github.com/containers/qm/tree/main) package for
isolating quality-managed code in a separate partition. When you enable QM, OSBuild builds two pipelines -
one for the regular filesystem, and one for the QM partition. In the final image, the QM root
filesystem is accessible in `/usr/share/qm/rootfs`.

Example manifest:

```yaml
name: qm-example
content:
  rpms:
    - curl
qm:
  content:
    rpms:
      - httpd
    systemd:
      enabled_services:
        - httpd.service
```

## Embedding containers in images

You can embed container images in the operating system image. These container images are automatically
available to podman in the running system. For example, use the following manifest to
pull the CentOS Stream 9 container image into the operating system:

```yaml
name: embed-container
content:
  rpms:
    - podman
  container_images:
    - source: quay.io/centos/centos
      tag: stream9
```

You can then configure these containers to run automatically in the system by using a
[quadlet.container](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) file
to start the container from systemd. You can view an example configuration in the
[examples/container.aib.yml](examples/container.aib.yml) file.

## Requesting new AIB manifest options

You can request support for additional AIB options by opening an issue in `the automotive-image-builder` repository:

1. Create an issue to request a new option.
1. Share a link to the issue in the `#automotive-image-builder` Slack channel.
1. Solicit feedback from the AIB team on the legitimacy and prioritization of the request. If accepted, the AIB team
   will triage, prioritize, and complete the work.
1. Track the issue to its resolution and close the ticket when a solution is implemented.
