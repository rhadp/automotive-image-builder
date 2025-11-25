#!/usr/bin/env python3

"""Argument parsing structures and utilities for automotive-image-builder."""

import argparse
import collections
import os
import platform
import sys

from .utils import DiskFormat
from .version import __version__
from . import log

# Default values used across arguments
default_distro = "autosd10-sig"
default_container_image_name = "quay.io/centos-sig-automotive/automotive-image-builder"
default_bib_container = "quay.io/centos-bootc/bootc-image-builder:latest"


def aib_build_container_name(distro):
    """Generate the name for an AIB build container."""
    return f"localhost/aib-build:{distro}"


# Registry for command callbacks
callbacks = {}


def command(name=None):
    """
    Decorator to register a function as a command callback.

    Usage:
        @command()  # Uses function name
        def build_bootc(tmpdir, runner):
            ...

        @command("custom_name")  # Uses custom name
        def some_function(tmpdir, runner):
            ...

    Args:
        name: Optional name to register this callback under.
              If None, uses the function's __name__

    Returns:
        The decorator function
    """

    def decorator(func):
        callback_name = name if name is not None else func.__name__
        callbacks[callback_name] = func
        return func

    return decorator


class AIBHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter that groups subcommands."""

    def _format_action(self, action):
        # Intercept the subparsers block and add subcommand groups
        if isinstance(action, argparse._SubParsersAction):
            sub_actions = {}
            for sub_action in action._get_subactions():
                name = getattr(sub_action, "dest", None)
                sub_actions[name] = sub_action

            groups = collections.defaultdict(list)
            for name, subp in action.choices.items():
                group = getattr(subp, "_group", "Commands")
                subaction = sub_actions[name]
                groups[group].append((name, subaction.help))

            # Render like argparse, but in grouped sections
            parts = []
            for group_name, entries in groups.items():
                parts.append(f"\n{group_name}:")
                maxlen = max(len(n) for n, _ in entries) if entries else 0
                for n, h in entries:
                    parts.append(
                        f"  {n.ljust(maxlen)}  {h if h != '==SUPPRESS==' else ''}"
                    )
            parts.append("")
            return "\n".join(parts)
        return super()._format_action(action)


def add_arg(parser, groups, name, data, suppress_default=False, suppress_help=False):
    """Add a single argument to a parser."""
    if isinstance(data, str):
        data = {"help": data}

    groupname = data.get("exclusive-group", None)
    if groupname:
        if groupname not in groups:
            groups[groupname] = parser.add_mutually_exclusive_group()
        dst = groups[groupname]
    else:
        dst = parser

    t = data.get("type", "bool" if name.startswith("-") else "str")

    # Determine default value (normal or SUPPRESS for subparsers)
    # SUPPRESS prevents subparsers from setting a default value, which would otherwise
    # overwrite any value already captured by the main parser. This allows shareable
    # arguments to work both before and after subcommands (e.g., both
    # `aib --container build ...` and `aib build --container ...`)
    if suppress_default:
        default = argparse.SUPPRESS
    elif t == "bool":
        default = False
    elif t == "append":
        default = []
    else:
        default = None

    if t == "bool":
        a = dst.add_argument(name, default=default, action="store_true")
    elif t == "bool-optional":
        # bool-optional doesn't need suppress_default handling
        a = dst.add_argument(name, action=argparse.BooleanOptionalAction)
    elif t == "diskformat":
        a = dst.add_argument(
            name,
            action="store",
            type=str,
            choices=[f.value for f in DiskFormat],
            default=default,
        )
    elif t == "version":
        # version doesn't need suppress_default handling
        a = dst.add_argument(name, action="version", version=f"%(prog)s {__version__}")
    elif t == "str" or t == "path":
        a = dst.add_argument(
            name,
            action="store",
            type=str,
            default=default,
        )
    elif t == "append":
        a = dst.add_argument(
            name,
            action="append",
            type=str,
            default=default,
        )
    else:
        log.error("Unknown arg type %s", t)

    if suppress_help:
        a.help = argparse.SUPPRESS
    elif "help" in data:
        a.help = data["help"]
    if "required" in data:
        a.required = data["required"]
    if "default" in data and not suppress_default:
        a.default = data["default"]
    if "metavar" in data:
        a.metavar = data["metavar"]
    elif t == "path":
        a.metavar = "PATH"


def add_args(parser, groups, args, suppress_default=False, suppress_help=False):
    """Add multiple arguments to a parser."""
    for name, data in args.items():
        add_arg(
            parser,
            groups,
            name,
            data,
            suppress_default=suppress_default,
            suppress_help=suppress_help,
        )


# Arguments for no subcommand
GLOBAL_ARGS = {
    "--version": {"type": "version"},
}

# Arguments for all subcommands
COMMON_ARGS = {
    "--verbose": {"help": "Print verbose output"},
}

# Shareable argument groups that can be used before or after subcommands (for historical reasons)
SHAREABLE_ARGS = {
    "container": {
        "--container": "Run build commands in a container (see --container-image-name)",
        "--user-container": "Use rootless containerized build",
        "--container-image-name": {
            "type": "str",
            "metavar": "IMAGE",
            "default": default_container_image_name,
            "help": f"Container image user for --container (default: {default_container_image_name})",
        },
        "--container-autoupdate": "Automatically pull new container image if available",
    },
    "include": {
        "--include": {
            "type": "append",
            "help": "Add include directory to extend available distros and targets",
        },
    },
}

LIST_ARGS = {"--quiet": {"help": "Only print the names, no descriptive text"}}

POLICY_ARGS = {
    "--policy": {
        "type": "str",
        "help": "Specify a policy file that restricts what build options are used",
        "exclusive-group": "policy",
    },
    "--fusa": {
        "help": argparse.SUPPRESS,
        "exclusive-group": "policy",
    },
}
TARGET_ARGS = {
    "--target": {
        "type": "str",
        "help": "Build for this target hardware board (see list-targets for options)",
    },
}
BUILD_ARGS = {
    "--distro": {
        "type": "str",
        "default": default_distro,
        "help": "Build for this distro specification and version (see list-distro for options)",
    },
    "--arch": {
        "default": platform.machine(),
        "type": "str",
        "help": f"Architecture to build for (default {platform.machine()})",
    },
    "--build-dir": {
        "type": "path",
        "default": os.getenv("OSBUILD_BUILDDIR"),
        "help": "Directory where intermediary files are stored",
    },
    "--cache-max-size": {
        "type": "str",
        "metavar": "SIZE",
        "help": "Max cache size inside build-dir, e.g. '8GB', or 'unlimited'",
    },
    "--cache": {
        "type": "str",
        "help": "Set dnf cache directory to use (default: none)",
    },
    "--logfile": {
        "type": "path",
        "default": None,
        "help": (
            "Path to file to write logs to. "
            "Default is <build-dir>/automotive-image-builder-[timestamp].log"
        ),
    },
    "--progress": {
        "type": "bool-optional",
        "help": "Enable or disable progress bar (default: enabled in terminal)",
        "default": sys.stdout.isatty(),
    },
    "--osbuild-manifest": {
        "type": "path",
        "help": "Path to store osbuild manifest that was used",
    },
    "--define": {
        "type": "append",
        "metavar": "KEY=VALUE",
        "help": "Define internal variable key to a specified value",
    },
    "--extend-define": {
        "type": "append",
        "metavar": "KEY=VALUE",
        "help": "Extend internal variable array by item or list",
    },
    "--define-file": {
        "type": "append",
        "metavar": "PATH",
        "help": "Add internal defines from a yaml dictionary in a file",
    },
    "--dump-variables": "Dump internal variables that would be used when building and exit.",
}
DISK_FORMAT_ARGS = {
    "--format": {
        "type": "diskformat",
        "help": "Disk image format (default: from extension)",
    },
    "--separate-partitions": {
        "help": "Split the resulting image into per-partition files",
    },
}

SHARED_RESEAL_ARGS = {
    "--build-container": {
        "type": "str",
        "help": "bootc build container image to use",
    },
    "--passwd": {
        "type": "str",
        "help": "openssl password source for --key, see openssl-passphrase-options manpage for format",
    },
}


def _get_build_subcommands():
    """Get build subcommand definitions with callbacks."""
    return [
        [
            "build-bootc",
            "Build a bootc container image (to container store or archive file)",
            "This builds a bootc-style container image from a manifest describing its\n"
            "content, and options like what board to target and what distribution version\n"
            "to use.\n"
            "\n"
            "The resulting container image can used to update a running bootc system, using\n"
            "`bootc update` or `bootc switch`. Or, alternatively it can be converted to a\n"
            "disk-image which can be flashed to a board using `bootc-to-disk-image`.\n",
            callbacks["build_bootc"],
            ["container", "include"],
            {
                "--user": {
                    "help": "Export container to per-user container storage (default: system storage)",
                },
                "--oci-archive": {
                    "help": "Build an oci container archive file instead of a container image",
                },
                "--tar": {
                    "help": "Build a tar file with the container content instead of a container image",
                },
                "--dry-run": {
                    "help": "Just compose the osbuild manifest, don't build it.",
                },
                "manifest": "Source manifest file",
                "out": "Output container image name (or pathname)",
            },
            POLICY_ARGS,
            TARGET_ARGS,
            BUILD_ARGS,
        ],
        [
            "build-traditional",
            "Build a traditional, package based, disk image file",
            "Builds a disk image from a manifest describing its content, and options like what\n"
            "board to target and what distribution version to use.\n"
            "\n"
            "By default this creates images that use rpm packages in a traditional writable\n"
            "filesystem. However, if you specify --ostree it will use ostree to make the\n"
            "root filesystem an immutable image. However, the later is a legacy option and\n"
            "it is recommended that new users use build-bootc instead.\n",
            callbacks["build_traditional"],
            ["container", "include"],
            DISK_FORMAT_ARGS,
            {
                "--ostree": {
                    "help": "Build a legacy osbuild image instead of package based"
                },
                "--ostree-repo": {
                    "type": "path",
                    "help": "Export ostree commit to ostree repo at this path",
                },
                "--dry-run": {
                    "help": "Just compose the osbuild manifest, don't build it.",
                },
                "manifest": "Source manifest file",
                "out": "Output path",
            },
            POLICY_ARGS,
            TARGET_ARGS,
            BUILD_ARGS,
        ],
        [
            "build-bootc-builder",
            "Build helper bootc image used by bootc-to-disk-image",
            "This command produces a bootc image containing required tools that is used\n"
            "in the bootc-to-disk-image (and bootc-reseal) command. This will contain tools\n"
            "like mkfs.ext4 that are needed to build a disk image.\n"
            "\n"
            "In non-automotive use of bootc, these tools are in the bootc image itself,\n"
            "but since automotive images are very minimal these need to come from another\n"
            "source. The tools need to match the version of the image, so these\n"
            "containers are built for specific distro versions.\n"
            "\n"
            "The container to use in bootc-to-disk-image can be specified with --build-container,\n"
            "but normally the default name of 'localhost/aib-build:$DISTRO' is used, and if\n"
            "the out argument is not specified this will be used.\n",
            callbacks["build_bootc_builder"],
            ["container", "include"],
            BUILD_ARGS,
            {
                "--if-needed": {
                    "help": "Only build the image if its not already built.",
                },
                "out": {"help": "Name of container image to build", "required": False},
            },
        ],
        [
            "build",
            "Backwards compatible a-i-b 1.0 build command (deprecated)",
            "Backwards compatibility command to build various types of images.\n"
            "This takes '--mode' and '--export' options that together define\n"
            "what to build and how.\n"
            "\n"
            "This command is deprecated, and we now recommend using 'build-bootc'\n"
            "or 'build-traditional' instead, as these are easier to use, and\n"
            "avoid accidentally using problematic combination of image options\n",
            callbacks["build"],
            ["container", "include"],
            {
                "--mode": {
                    "type": "str",
                    "default": "image",
                    "help": "Build this image mode (package, image)",
                },
                "--ostree-repo": {
                    "type": "path",
                    "help": "Export ostree commit to ostree repo at this path",
                },
                "--export": {
                    "type": "append",
                    "help": "Export this image type",
                },
                "manifest": "Source manifest file",
                "out": "Output path",
            },
            POLICY_ARGS,
            TARGET_ARGS,
            BUILD_ARGS,
        ],
    ]


def _get_bootc_subcommands():
    """Get bootc subcommand definitions with callbacks."""
    return [
        [
            "bootc-to-disk-image",
            "Build a physical disk image based on a bootc container",
            "Converts a bootc container image to a disk image that can be flashed on a board\n"
            "\n"
            "Internally this uses the bootc-image-builder tool from a container image.\n"
            "The --bib-container option can be used to specify a different version of this tool\n"
            "\n"
            "Also, to build the image we need a container with tools. See the build-bootc-builder\n"
            "command for how to build one.\n",
            callbacks["bootc_to_disk_image"],
            [],
            DISK_FORMAT_ARGS,
            {
                "--bib-container": {
                    "type": "str",
                    "metavar": "IMAGE",
                    "default": default_bib_container,
                    "help": f"bootc-image-builder image to use (default: {default_bib_container})",
                },
                "--build-container": {
                    "type": "str",
                    "metavar": "IMAGE",
                    "help": f"bootc build container image to use  (default: {aib_build_container_name('$DISTRO')})",
                },
                "src_container": "Bootc container name",
                "out": "Output image name",
            },
        ],
        [
            "bootc-extract-for-signing",
            "Extract files for secure-boot signing",
            "Extract all the files related to secure boot that need signing in the image. This can\n"
            "be for example EFI executables, or aboot partition data.\n"
            "\n"
            "These files can then be signed, using whatever process available to the user, which\n"
            "often involves sending them to a 3rd party. Once these files are signed, the modified\n"
            "file can then be injected using bootc-inject-signed.\n",
            callbacks["bootc_extract_for_signing"],
            [],
            {
                "src_container": "Bootc container name",
                "out": "Output directory",
            },
        ],
        [
            "bootc-inject-signed",
            "Inject files that were signed for secure-boot",
            "Once the files produced by bootc-extract-for-signing have been signed, this command\n"
            "can be used to inject them into the bootc image again.\n"
            "\n"
            "Note that this modified the bootc image which makes it not possible to boot if\n"
            "sealed images are being used (which is the default). Also, signatures interact\n"
            "in a complex way with sealing. See the help for bootc-reseal for how to re-seal\n"
            "the modified image so that it boots again.\n",
            callbacks["bootc_inject_signed"],
            [],
            {
                "src_container": "Bootc container name",
                "srcdir": "Directory with signed files",
                "new_container": "Destination container name",
            },
        ],
        [
            "bootc-reseal",
            "Seal bootc image after it has been modified",
            "By default, bootc images are 'sealed', which means that the root filesystem\n"
            "is signed by a secret key. The (signed by secureboot) initramfs will contain\n"
            "the corresponding public key used to validate the root filesystem. If a\n"
            "bootc image is built to be sealed and it is later modified then this check\n"
            "will fail and the image will not boot. The bootc-reseal operation fixes this\n"
            "by updating the initramfs with a new public key and signing the rootfs with\n"
            "the (temporary) private key.\n"
            "\n"
            "Note: Re-sealing modifies the initramfs, which interacts badly with secureboot,\n"
            "where the initramfs is signed by a trusted key. To fix this issue there is a\n"
            "separate command 'bootc-prepare-reseal' that does the initial step of bootc-reseal\n"
            "i.e., it adds a new public key to the initrd. Once that is done, you can sign the\n"
            "new initramfs and then finish with bootc-prepare-reseal, passing in the key used\n"
            "in bootc-prepare-reseal to bootc-reseal with the --key option. See the help for\n"
            "bootc-prepare-reseal for more details\n",
            callbacks["bootc_reseal"],
            [],
            SHARED_RESEAL_ARGS,
            {
                "--key": {
                    "type": "path",
                    "help": "path to private key, as previously used in bootc-prepare-reseal",
                },
                "src_container": "Bootc container name",
                "new_container": "Destination container name",
            },
        ],
        [
            "bootc-prepare-reseal",
            "Do the initial step of sealing and image, allowing further changes before actually sealing",
            "Injects the public part of a key pair into the initramfs of the bootc image, to\n"
            "prepare for signinging the initrd, and later calling bootc-reseal.\n"
            "\n"
            "The private key supplied should be single-use, used only for one image and discarded after\n"
            "it has been used in the matching bootc-reseal operation.\n"
            "\n"
            "A private key can be generated with openssl like this:\n"
            "   openssl genpkey -algorithm ed25519 -outform PEM -out private.pem\n"
            "Optionally, `-aes-256-cbc` can be added to encrypt the private key with a password (which\n"
            "then has to be supplied when using it).\n"
            "\n",
            callbacks["bootc_prepare_reseal"],
            [],
            SHARED_RESEAL_ARGS,
            {
                "--key": {
                    "type": "path",
                    "help": "path to private key file.",
                    "required": True,
                },
                "src_container": "Bootc container name",
                "new_container": "Destination container name",
            },
        ],
    ]


def _get_subcommands():
    """Get other subcommand definitions with callbacks."""
    return [
        [
            "list-distro",
            "list available distributions",
            "List all the available distributions available for --distro.",
            callbacks["list_distro"],
            ["include"],
            LIST_ARGS,
        ],
        [
            "list-targets",
            "list available targets",
            "List all the available targets available for --target.",
            callbacks["list_targets"],
            ["include"],
            LIST_ARGS,
        ],
        [
            "list-rpms",
            "List the rpms that a manifest would use when built",
            "List the rpms that a manifest would use when build",
            callbacks["listrpms"],
            ["container", "include"],
            TARGET_ARGS,
            BUILD_ARGS,
            {
                # TODO: We should drop --mode when build command is dropped
                "--mode": {
                    "type": "str",
                    "default": "image",
                    "help": "Build this image mode (package, image)",
                },
                "manifest": "Source manifest file",
            },
        ],
        [
            "download",
            "Download all sources that are needed to build an image",
            "This downloads all the source files that would be downloaded when an image is built\n"
            "It is a good way to pre-seed a --build-dir that is later used with multiple image\n"
            "builds.\n",
            callbacks["download"],
            [],
            TARGET_ARGS,
            BUILD_ARGS,
            {
                "manifest": "Source manifest file",
            },
        ],
    ]


def _get_subcommand_groups(callbacks):
    """Get all subcommand groups with callbacks."""
    return [
        ["Basic image building", _get_build_subcommands()],
        ["Bootc operations", _get_bootc_subcommands()],
        ["Other commands", _get_subcommands()],
    ]


def parse_args(args, base_dir):
    """
    Parse command-line arguments.

    Args:
        args: List of command-line arguments to parse
        base_dir: Base directory for the project

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="automotive-image-builder",
        description="Select subcommand to run.\n"
        "For more details, use --help for the individual commands.",
        formatter_class=AIBHelpFormatter,
    )
    parser._positionals.title = None
    parser._optionals.title = "Global options"
    add_args(parser, {}, GLOBAL_ARGS)
    add_args(parser, {}, COMMON_ARGS)
    # Add shareable args to main parser with normal defaults, but no help
    for arg_dict in SHAREABLE_ARGS.values():
        add_args(parser, {}, arg_dict, suppress_default=False, suppress_help=True)
    parser.set_defaults(func=callbacks["no_subcommand"])

    subcommand_groups = _get_subcommand_groups(callbacks)
    subparsers = parser.add_subparsers()
    for g in subcommand_groups:
        group_text = g[0]
        for s in g[1]:
            arg_groups = {}
            name = s[0]
            helptext = s[1]
            description = s[2]
            callback = s[3]
            # List of shareable arg keys like ["container", "include"]
            shareable_args = s[4]
            subcmd_args = s[5:]

            subparser = subparsers.add_parser(
                name,
                help=helptext,
                description=description,
                formatter_class=argparse.RawDescriptionHelpFormatter,
            )
            subparser.set_defaults(func=callback)
            subparser._group = group_text

            # Add remaining args
            for _args in subcmd_args:
                add_args(subparser, arg_groups, _args)

            # Add shareable args to subparser with SUPPRESS default to preserve main parser values
            # This allows arguments to work in both positions without overwriting each other
            add_args(subparser, {}, COMMON_ARGS, suppress_default=True)
            for key in shareable_args:
                add_args(
                    subparser, arg_groups, SHAREABLE_ARGS[key], suppress_default=True
                )

    res = parser.parse_args(args)
    if "manifest" in res:
        if (
            res.manifest.endswith(".aib")
            or res.manifest.endswith(".aib.yml")
            or res.manifest.endswith(".aib.yaml")
        ):
            res.simple_manifest = res.manifest
            res.manifest = os.path.join(base_dir, "files/simple.mpp.yml")

    return res
