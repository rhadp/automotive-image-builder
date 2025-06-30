# Automotive image builder

Automotive image builder is a tool to create various kinds of OS images based on CentOS derived
distributions. The images can support package-based mode (called "package") as well as image-based mode
(called "image").

The main tool is called `automotive-image-builder`, and the basic operation it does is called
"composing" manifests. The compose operation takes a yaml-based automotive image manifest, as well
as a set of options affecting the compose and resolves the manifest into an osbuild json file. This
json file is a precise build instruction for how to build an image with osbuild with the very
specific software that was chosen during the compose. For example, the version of selected packages
and container images is chosen during the compose.

To build a qcow2 image you can run:

```shell
 $ automotive-image-builder compose --distro autosd9 --mode package --target qemu my-image.aib.yml osbuild.json
 $ sudo osbuild --store osbuild_store --output-directory output --export qcow2 osbuild.json
```

You can also combine these two in one command:

```shell
 $ automotive-image-builder build --distro autosd9 --mode package --target qemu --export qcow2 my-image.aib.yml osbuild.json
```

These will first compose the osbuild.json file, and then build it and export the "qcow2" output,
which will end up in the "output" directory (in particular as `output/qcow2/disk.qcow2`). Qcow images
are typically run in a virtual machine, which you can easily do using:

```shell
 $ automotive-image-runner  output/qcow2/disk.qcow2
```

Note: when running `automotive-image-builder build` it is very helpful
to pass also the option `--build-dir some/dir`, as that will then store intermediate data, such as downloaded
rpms between runs, which saves a lot of time.

## Manifests

automotive-image-builder supports two types of image manifests. The
default manifest uses the extension `.aib.yml` and is a high-level,
declarative YAML-based format.

A example of such a manifest looks like this:
```yaml
name: image-with-vim

content:
  rpms:
    - vim
```


You can find detailed [schema documentation for the manifest syntax]
(https://centos.gitlab.io/automotive/src/automotive-image-builder/simple_manifest.html).

You can also experiment with the example manifests in the [examples](examples) directory:

```shell
$ automotive-image-builder build --export qcow2 examples/simple.aib.yml example.qcow2
$ automotive-image-runner example.qcow2
```

The sample-images repository
(https://gitlab.com/CentOS/automotive/sample-images) has a larger set
of functional examples.

There is also support for a lowlevel manifest file format, with extension `.mpp.yml`. This is
a format closer to the osbuild imperative format, and writing such files requires deeper
knowledge of how osbuild works, as well as the internals of automotive-image-builder. This
is used internally to implement the higher level manifest format, but it is also available
to the end user. However, we don't recommend using this format as it is quite hard to use
and not well documented.

## Controlling the image built

When composing (or building) a manifest there are some core options that control what gets built:

* `--arch`: The hardware architecture to build for (`x86_64` or `aarch64`). If not specified the native
   architecture is used. Note: It is possible to compose an image for any architecture, but you can
   only build one for the native architecture.

* `--target`: The board to target, defaults to `qemu`. You can get a list of the supported targets from
 `automotive-image-builder list-targets`.

* `--mode`: Either "`package`" or "`image`". Default is `image`. Package mode is a read-write OS based on
  dnf to install package. Image mode is an immutable OS image based on ostree that supports
  atomically updates, but no modification on the package level. Image mode is meant to be used in
  production, but package mode is more useful when doing development and testing.

* `--distro`: There are a set of distribution definitions that can be used. These define what package
  repositories to use. The default used in "autosd9-sig", but the full list can be gotten with
  `automotive-image-builder list-dist`.  It is also possible to extend the list of distributions
  with your custom ones by putting them in a directory called "/some/dir/distro" and passing
  `--include /some/dir` on the argument list.

When the manifest has been composed, the generated osbuild json file can contain several types of
things that can be build. For example, it can generate both raw image files and qcow2 files. When
building you need to the `--export` option to select what you want to build. The available exports
are:

* `image`: A raw disk image with partitions
* `qcow2`: A qcow2 format disk image with partitions
* `ext4`: An ext4 filesystem containing just the rootfs partition (i.e. no boot partitions, etc)
* `aboot`: An android boot system partition image and a boot partition
* `container`: A container image you can run with podman or docker
* `tar`: A tar file containing the basic rootfs files
* `ostree-commit`: An ostree repo with the commit built from the image
* `bootc`: A bootc image
* `rpmlist`: A json file listing all the rpms used in the image

## Manifest variables

The low-level manifest format supports a variety of variables that you can set in the manifest file, or
on the command line. In the high-level manifests, these are automatically set based on the options in
the manifest and the target/distro/mode that you choose, although it can sometimes be useful to
modify these variables on the command line during development and testing.

To modify these variables on the command line, you can use the following options:

* `--define VAR=VALUE`: Sets the variable to the specified value, which is a yaml value.

* `--define-file PATH`: Loads variables from a yaml dict in a file, where the keys are variable names.

* `--extend-define VAR=VALUE`: Similar to `--define`, but this is only useable for list-based variable
  and will extend the list already in the variable (or start a new list if it is unset). This
  support specifying either a list value or just a plain item value.

Here are some commonly used variable supported and what they mean:

* `use_qm`: If this is true, then the support for the qm partion is included in the image
* `qm_memory_max`: Set the maximum memory that can be used by the QM partition (see MemoryMax systemd option for format)
* `use_bluechi_agent`: If this is true, then the support for bluechi-agent is included and configured in the host and (if enabled) in the qm partition
* `use_bluechi_controller`: If this is true, then the support for bluechi-controller is included and configured in the host
* `extra_rpms`: Many manifests (e.g. in sample-images) support this variable to add extra rpms to the image
* `image_size`: Specifies the size in bytes (as a string) of the generated image
* `use_composefs_signed`: If this is set to false, then use of ostree will not require signed commits. This can be needed in some cases if you want to modify the ostree image on the target system (e.g. layering packages).
* `use_transient_etc`: If this is set to false, then changes to `/etc` will be persisted over boot on image based builds. This is not recommended in production, but can be useful during testing.
* `use_static_ip`: If this is set, then NetworkManager is not used and the below set of options specify the hardcoded network config:
* `static_ip`: The ip address
* `static_gw`: The default gateway ip
* `static_dns`: The dns server ip
* `static_ip_iface`: The network interface name
* `static_ip_modules`: The network driver kernel modules to load (if any)
* `bluechi_controller_host_ip`: The IP address of the bluechi controller (used by bluechi-agents)
* `bluechi_nodename`: The node name of the bluechi-agent on the image (qm agent gets "qm." prepended to name)
* `bluechi_controller_allowed_node_names`: A list of node names accepted by the bluechi controller
* `use_debug`: If set to true, a lot more debugging info will be shown during boot

## Using qm

`automotive-image-builder` supports the [QM](https://github.com/containers/qm/tree/main) package for
isolating quality-managed code in a separate partition. When you enable qm, OSBuild builds two pipelines -
one for the regular filesystem, and one for the qm partition. In the final image the qm root
filesystem will be accessible under `/usr/share/qm/rootfs`.

For example, use the following manifest to install and run httpd in the qm partition:

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

You can embed container images in the operating system image. These images are automatically
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

You can request support for additional AIB options by opening an issue in the automotive-image-builder repo:

1. Create an issue to request a new option.
1. Share a link to the issue in the #automotive-image-builder Slack channel.
1. Solicit feedback from AIB team on the legitimacy and prioritization of the request. If your request is accepted, the AIB team 
   will triage, prioritize, and complete the work.
1. Track the issue to its resolution and close the ticket when a solution is implemented.
