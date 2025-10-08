#!/usr/bin/env python3

import argparse
import base64
import sys
import os
import platform
import json
import tempfile
import shutil
import yaml

from .utils import extract_comment_header, get_osbuild_major_version
from .exports import export, EXPORT_DATAS, get_export_data
from .runner import Runner
from .ostree import OSTree
from .simple import ManifestLoader
from .version import __version__
from . import exceptions
from . import AIBParameters
from . import log
from . import vmhelper
from .podman import (
    podman_image_exists,
    podman_image_info,
    podman_run_bootc_image_builder,
    PodmanImageMount,
)

default_distro = "autosd10-sig"
default_container_image_name = "quay.io/centos-sig-automotive/automotive-image-builder"
base_dir = os.path.realpath(sys.argv[1])
default_bib_container = "quay.io/centos-bootc/bootc-image-builder:latest"


def list_ipp_items(args, item_type):
    items = {}
    for inc in args.include_dirs:
        subdir = os.path.join(inc, item_type)
        for f in os.listdir(subdir):
            if f.endswith(".ipp.yml"):
                item = f[:-8]
                if item not in items:
                    items[item] = os.path.join(subdir, f)
    for d in sorted(items.keys()):
        if args.quiet:
            print(d)
        else:
            path = items[d]
            if os.path.islink(path):
                target = os.readlink(path)
                alias = os.path.basename(target).removesuffix(".ipp.yml")
                desc = f"Alias of '{alias}'"
            else:
                with open(path, mode="r") as file:
                    header = extract_comment_header(file)
                paras = header.split("\n\n")
                desc = paras[0].replace("\n", " ")

            print(f"{d} - {desc}")


def list_dist(args, _tmpdir, _runner):
    list_ipp_items(args, "distro")


def list_targets(args, _tmpdir, _runner):
    list_ipp_items(args, "targets")


def list_exports(args, _tmpdir, _runner):
    exports = EXPORT_DATAS.keys()
    for d in sorted(exports):
        if args.quiet:
            print(d)
        else:
            print(f"{d} - {EXPORT_DATAS[d].get('desc', '')}")


def parse_define(d, option):
    parts = d.split("=", 1)
    if len(parts) != 2:
        raise exceptions.InvalidOption(option, d)
    k = parts[0]
    yaml_v = parts[1]
    try:
        v = yaml.safe_load(yaml_v)
    except yaml.parser.ParserError as e:
        raise exceptions.InvalidOption(option, yaml_v) from e
    return k, v


def make_embed_path_abs(stage, path):
    for k, v in stage.items():
        try:
            embed_path = v["path"]
        except (KeyError, TypeError):
            if isinstance(v, dict):
                make_embed_path_abs(v, path)
            continue

        if k == "mpp-embed" and not os.path.isabs(embed_path):
            v["path"] = os.path.normpath(
                os.path.join(os.path.abspath(path), embed_path)
            )


def rewrite_manifest(manifest, path):
    pipelines = manifest.get("pipelines")
    if not pipelines:
        raise exceptions.MissingSection("pipelines")

    rootfs = None
    for p in pipelines:
        if p.get("name") == "rootfs":
            rootfs = p
        for stage in p.get("stages", []):
            make_embed_path_abs(stage, path)

    # Also, we need to inject some workarounds in the rootfs stage
    if rootfs and "stages" in rootfs:
        rootfs["stages"] = [
            {"mpp-eval": "init_rootfs_dirs_stage"},
            # See comment in kernel_cmdline_stage variable
            {"mpp-eval": "kernel_cmdline_stage"},
            {"mpp-eval": "init_rootfs_files_stage"},
        ] + rootfs.get("stages", [])


def strip_ext(path):
    return os.path.splitext(os.path.splitext(path)[0])[0]


def validate_policy_args(args):
    """Validate build arguments against policy restrictions."""
    if args.policy:
        # Validate build arguments
        errors = args.policy.validate_build_args(
            args.mode, args.target, args.distro, args.arch
        )
        if errors:
            raise exceptions.AIBException(
                "Policy validation failed:\n" + "\n".join(errors)
            )


def create_osbuild_manifest(args, tmpdir, out, runner):
    validate_policy_args(args)

    with open(args.manifest) as f:
        try:
            manifest = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise exceptions.ManifestParseError(args.manifest) from exc

    rewrite_manifest(manifest, os.path.dirname(args.manifest))

    runner.add_volume_for(args.manifest)
    runner.add_volume_for(out)

    defines = {
        "_basedir": args.base_dir,
        "_workdir": tmpdir,
        "name": manifest.get("mpp-vars", {}).get(
            "name", strip_ext(os.path.basename(args.manifest))
        ),
        "arch": args.arch,
        "target": args.target,
        "distro_name": args.distro,
        "image_mode": args.mode,
        "osbuild_major_version": get_osbuild_major_version(
            runner, use_container=(args.vm or args.container)
        ),
        # This is a leftover for backwards compatibilty:
        "image_type": "ostree" if args.mode == "image" else "regular",
    }

    if args.dump_variables:
        defines["print_variables"] = True

    defines["exports"] = args.export if args.export else []

    # Add policy-derived variables
    if args.policy:
        policy = args.policy

        # Add forced variables from policy
        forced_vars = policy.get_forced_variables()
        defines.update(forced_vars)

        # Add denylist variables
        defines["policy_denylist_rpms"] = policy.disallowed_rpms
        defines["policy_denylist_modules"] = policy.disallowed_kernel_modules

        # Add sysctl options
        sysctl_options = []
        for key, value in policy.get_forced_sysctl().items():
            sysctl_options.append({"key": key, "value": value})
        defines["policy_systemctl_options"] = sysctl_options

        # Add SELinux booleans
        selinux_booleans = []
        for key, value in policy.get_forced_selinux_booleans().items():
            bool_str = "true" if value else "false"
            selinux_booleans.append(f"{key}={bool_str}")
        defines["policy_selinux_booleans"] = selinux_booleans

    if args.simple_manifest:
        loader = ManifestLoader(defines, args.policy)

        loader.load(args.simple_manifest, os.path.dirname(args.simple_manifest))

    if args.ostree_repo:
        runner.add_volume_for(args.ostree_repo)

        ostree = OSTree(args.ostree_repo, runner)
        revs = {}
        for ref in ostree.refs():
            rev = ostree.rev_parse(ref)
            revs[ref] = rev
        defines["ostree_parent_refs"] = revs

    for d in args.define:
        k, v = parse_define(d, "--define")
        defines[k] = v

    for df in args.define_file:
        try:
            with open(df) as f:
                file_defines = yaml.safe_load(f)
            if not isinstance(file_defines, dict):
                raise exceptions.DefineFileError("Define file must be yaml dict")
            for k, v in file_defines.items():
                defines[k] = v
        except yaml.parser.ParserError as e:
            raise exceptions.DefineFileError(
                f"Invalid yaml define file '{df}': {e}"
            ) from e

    for d in args.extend_define:
        k, v = parse_define(d, "--extend-define")
        if not isinstance(v, list):
            v = [v]
        if k not in defines:
            defines[k] = []
        defines[k].extend(v)

    cmdline = [args.osbuild_mpp]
    for inc in args.include_dirs:
        cmdline += ["-I", inc]

    for k in sorted(defines.keys()):
        v = defines[k]
        cmdline += ["-D", f"{k}={json.dumps(v)}"]

    for arg in args.mpp_arg:
        cmdline += [arg]

    if args.cache:
        cmdline += ["--cache", args.cache]
    else:
        # By default we use an isolated dnf cache to avoid stale caches
        cmdline += ["--cache", os.path.join(tmpdir, "dnf-cache")]

    variables_manifest = {
        "version": manifest["version"],
        "mpp-vars": manifest.get("mpp-vars", {}),
    }

    rewritten_manifest_path = os.path.join(tmpdir, "manifest-variables.ipp.yml")
    with open(rewritten_manifest_path, "w") as f:
        yaml.dump(variables_manifest, f, sort_keys=False)

    del manifest["mpp-vars"]

    rewritten_manifest_path = os.path.join(tmpdir, "manifest.ipp.yml")
    with open(rewritten_manifest_path, "w") as f:
        yaml.dump(manifest, f, sort_keys=False)

    cmdline += [os.path.join(args.base_dir, "include/main.ipp.yml"), out]

    runner.run_as_user(cmdline)


def compose(args, tmpdir, runner):
    return create_osbuild_manifest(args, tmpdir, args.out, runner)


def extract_rpmlist_json(osbuild_manifest):
    with open(osbuild_manifest) as f:
        d = json.load(f)

    pipelines = d["pipelines"]
    rpmlist = None
    for p in pipelines:
        if p.get("name") == "rpmlist":
            rpmlist = p
            break
    inline_digest = list(rpmlist["stages"][0]["inputs"]["inlinefile"]["references"])[0]

    inline_items = d["sources"]["org.osbuild.inline"]["items"]
    data_b64 = inline_items[inline_digest]["data"]
    return base64.b64decode(data_b64).decode("utf8")


def listrpms(args, tmpdir, runner):
    osbuild_manifest = os.path.join(tmpdir, "osbuild.json")

    create_osbuild_manifest(args, tmpdir, osbuild_manifest, runner)

    data = extract_rpmlist_json(osbuild_manifest)

    print(data)


def _build(args, tmpdir, runner):
    runner.add_volume_for(args.out)

    osbuild_manifest = os.path.join(tmpdir, "osbuild.json")
    if args.osbuild_manifest:
        osbuild_manifest = args.osbuild_manifest

    create_osbuild_manifest(args, tmpdir, osbuild_manifest, runner)

    builddir = tmpdir
    if args.build_dir:
        builddir = args.build_dir
        os.makedirs(builddir, exist_ok=True)
    runner.add_volume(builddir)
    runner.add_volume("/dev")

    cmdline = ["osbuild"]

    outputdir = os.path.join(builddir, "image_output")
    os.makedirs(outputdir, exist_ok=True)
    cmdline += [
        "--store",
        os.path.join(builddir, "osbuild_store"),
        "--output-directory",
        outputdir,
    ]

    if args.build_dir:
        # Cache stuff between builds
        cmdline += [
            "--checkpoint",
            "build",
            "--checkpoint",
            "qm_rootfs_base",
            "--checkpoint",
            "qm_rootfs",
            "--checkpoint",
            "data",
        ]

    if args.cache_max_size:
        cmdline += ["--cache-max-size=" + args.cache_max_size]

    if args.progress:
        # Add JSONSeqMonitor for progress monitoring
        cmdline += ["--monitor", "JSONSeqMonitor"]

    has_repo = False
    exports = []
    # Rewrite exports according to export_data
    for exp in args.export:
        data = get_export_data(exp)
        exp = data.get("export_arg", exp)
        exports.append(exp)
        if exp == "ostree-commit":
            has_repo = True

    # If ostree repo was specified, also export it if needed
    if not has_repo and args.ostree_repo:
        exports += ["ostree-commit"]

    if args.vm:
        # Download sources on host, using no exports

        cmdline += [osbuild_manifest]
        runner.run_in_container(cmdline, progress=args.progress, verbose=args.verbose)

        # Now do the build in the vm

        shutil.copyfile(osbuild_manifest, os.path.join(builddir, "manifest.json"))

        with open(osbuild_manifest) as f:
            d = json.load(f)
            curl_items = d.get("sources", {}).get("org.osbuild.curl", {})
            curl_files = curl_items.get("items", {}).keys()
            with open(os.path.join(builddir, "manifest.files"), "w") as f2:
                f2.write("\n".join(curl_files))

        kernel = f"aibvm-{args.arch}.vmlinux"
        rootimg = f"aibvm-{args.arch}.qcow2"

        # TODO: Should these be in builddir?
        var_image = os.path.join(builddir, f"aibvm-var-{args.arch}.qcow2")
        escaped_image = args.container_image_name.replace("/", "_")
        container_file = os.path.join(
            builddir, f"aibvm-{escaped_image}-{args.arch}.tar"
        )

        if not os.path.isfile(var_image):
            vmhelper.mk_var(var_image)

        if not os.path.isfile(container_file):
            vmhelper.get_container(container_file, args.arch, args.container_image_name)

        output_tar = os.path.join(builddir, "output.tar")
        try:
            # Ensure no leftover from earlier build
            os.remove(output_tar)
        except OSError:
            pass

        res = vmhelper.run_vm(
            args.arch,
            kernel,
            rootimg,
            var_image,
            container_file,
            builddir,
            os.path.join(args.base_dir, "files/aibvm-run"),
            "4G",
            args.container_image_name,
            f"EXPORTS={','.join(exports)}",
        )
        if res != 0:
            sys.exit(1)  # vm will have printed the error

        runner.run_as_root(["tar", "xvf", output_tar, "-C", outputdir])
    else:
        for exp in exports:
            cmdline += ["--export", exp]

        cmdline += [osbuild_manifest]

        runner.run_in_container(
            cmdline,
            need_osbuild_privs=True,
            progress=args.progress,
            verbose=args.verbose,
        )

    if args.ostree_repo:
        repodir = os.path.join(outputdir, "ostree-commit/repo")
        runner.run_as_user(
            ["ostree", "pull-local", "--repo=" + args.ostree_repo, repodir]
        )

    if len(args.export) == 1:
        # Export directly to args.out
        export(outputdir, args.out, False, args.export[0], runner)
    else:
        if os.path.isdir(args.out) or os.path.isfile(args.out):
            runner.run_as_root(["rm", "-rf", args.out])
        os.mkdir(args.out)
        for exp in args.export:
            export(outputdir, args.out, True, exp, runner)

    runner.run_as_root(["rm", "-rf", outputdir])


def build(args, tmpdir, runner):
    try:
        _build(args, tmpdir, runner)
    finally:

        # Ensure we can clean up these directories, that can have
        # weird permissions
        if os.path.isdir(os.path.join(tmpdir, "osbuild_store")) or os.path.isdir(
            os.path.join(tmpdir, "image_output")
        ):
            runner.run_as_root(["rm", "-rf", tmpdir])


def build_bootc_builder(args, tmpdir, runner):
    # build-bootc-builder is a special form of the "build" command with fixed values for
    # manifest/export/target/mode arguments.
    args.simple_manifest = os.path.join(args.base_dir, "files/bootc-builder.aib.yml")
    args.manifest = os.path.join(args.base_dir, "files/simple.mpp.yml")
    args.export = ["bootc"]
    args.target = "qemu"
    args.mode = "image"
    print(args.manifest)
    build(args, tmpdir, runner)


def bootc_to_disk_image(args, tmpdir, runner):
    info = podman_image_info(args.src_container)
    if not info:
        log.error(
            "Source bootc image '%s' isn't in local container store", args.src_container
        )
        sys.exit(1)

    # Use same distro for build image as the source container image
    distro = default_distro
    if info.build_info:
        distro = info.build_info.get("DISTRO", distro)

    build_container = args.build_container
    if not build_container:
        build_container = f"localhost/auto-bootc-build-{distro}:latest"
        if not podman_image_exists(build_container):
            log.error(
                "Build container %s isn't in local container stored", build_container
            )
            log.error(
                "Either specify another with --build-container, or create it using: "
            )
            log.error(
                " automotive-image-builder build-bootc-builder --distro %s %s",
                distro,
                build_container,
            )
            sys.exit(1)

    build_type = "raw"
    if args.out.endswith(".qcow2"):
        build_type = "qcow2"

    res = podman_run_bootc_image_builder(
        args.bib_container, build_container, args.src_container, build_type, args.out
    )
    if res != 0:
        sys.exit(1)  # bc-i-b will have printed the error


def bootc_extract_for_signing(args, tmpdir, runner):
    if not podman_image_exists(args.src_container):
        log.error(
            "Source bootc image '%s' isn't in local container store", args.src_container
        )
        sys.exit(1)
    os.makedirs(args.out, exist_ok=True)
    with PodmanImageMount(args.src_container) as mount:
        if mount.has_file("/etc/signing_info.json"):
            content = mount.read_file("/etc/signing_info.json")
            info = json.loads(content)

            with open(os.path.join(args.out, "signing_info.json"), "a") as f:
                f.write(content)
            for f in info.get("signed_files", []):
                _type = f["type"]
                filename = f["filename"]
                src = f["paths"][0]  # All files should be the same, copy out first

                if _type == "efi":
                    destdir = os.path.join(args.out, "efi")
                else:
                    log.error("Unknown signature type {_type}")
                    sys.exit(1)

                os.makedirs(destdir, exist_ok=True)

                log.info("Extracting %s from %s", filename, src)
                dest = os.path.join(destdir, filename)
                mount.copy_out_file(src, dest)
        else:
            log.info("No /etc/signing-info.json, nothing to sign")
            sys.exit(0)


def bootc_inject_signed(args, tmpdir, runner):
    if not podman_image_exists(args.src_container):
        log.error(
            "Source bootc image '%s' isn't in local container store", args.src_container
        )
        sys.exit(1)

    with PodmanImageMount(
        args.src_container, writable=True, commit_image=args.new_container
    ) as mount:
        if mount.has_file("/etc/signing_info.json"):
            content = mount.read_file("/etc/signing_info.json")
            info = json.loads(content)

            for f in info.get("signed_files", []):
                _type = f["type"]
                filename = f["filename"]

                if _type == "efi":
                    srcdir = os.path.join(args.srcdir, "efi")
                else:
                    log.error("Unknown signature type {_type}")
                    sys.exit(1)

                src = os.path.join(srcdir, filename)
                log.info("Injecting %s from %s", filename, src)

                for dest_path in f["paths"]:
                    mount.copy_in_file(src, dest_path)
        else:
            log.info("No /etc/signing-info.json, nothing needed signing")
            sys.exit(0)


def no_subcommand(_args, _tmpdir, _runner):
    log.info("No subcommand specified, see --help for usage")


def add_arg(parser, groups, name, data):
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
    if t == "bool":
        a = dst.add_argument(name, default=False, action="store_true")
    elif t == "bool-optional":
        a = dst.add_argument(name, action=argparse.BooleanOptionalAction)
    elif t == "version":
        a = dst.add_argument(name, action="version", version=f"%(prog)s {__version__}")
    elif t == "str":
        a = dst.add_argument(
            name,
            action="store",
            type=str,
        )
    elif t == "append":
        a = dst.add_argument(
            name,
            action="append",
            type=str,
            default=[],
        )
    else:
        log.error("Unknown arg type %s", t)

    if "help" in data:
        a.help = data["help"]
    if "required" in data:
        a.required = data["required"]
    if "default" in data:
        a.default = data["default"]


def add_args(parser, groups, args):
    for name, data in args.items():
        add_arg(parser, groups, name, data)


def parse_args(args, base_dir):
    parser = argparse.ArgumentParser(
        prog="automotive-image-builder", description="Build automotive images"
    )
    add_args(parser, {}, COMMON_ARGS)
    parser.set_defaults(func=no_subcommand)

    subparsers = parser.add_subparsers(help="sub-command help")
    for s in subcommands:
        groups = {}
        name = s[0]
        helptext = s[1]
        callback = s[2]
        subcmd_args = s[3:]
        subparser = subparsers.add_parser(name, help=helptext)
        subparser.set_defaults(func=callback)
        for _args in subcmd_args:
            add_args(subparser, groups, _args)

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


COMMON_ARGS = {
    "--version": {"type": "version"},
    "--verbose": {},
    "--container": "Use containerized build",
    "--user-container": "Use rootless containerized build",
    "--container-image-name": {
        "type": "str",
        "default": default_container_image_name,
        "help": f"Container image name, {default_container_image_name} is default if this option remains unused",
    },
    "--container-autoupdate": "Automatically pull new container image if available",
    "--include": {"type": "append", "help": "Add include directory"},
    "--vm": {},
}

LIST_ARGS = {"--quiet": {}}

# Shared arguments for formating mpp files, doesn't include options not used by build-bootc-builder
SHARED_FORMAT_ARGS = {
    "--arch": {
        "default": platform.machine(),
        "type": "str",
        "help": f"Arch to run for (default {platform.machine()})",
    },
    "--osbuild-mpp": {
        "type": "str",
        "default": os.path.join(base_dir, "mpp/aib-osbuild-mpp"),
        "help": "Use this osbuild-mpp binary",
    },
    "--distro": {
        "type": "str",
        "default": default_distro,
        "help": "Build for this distro specification",
    },
    "--mpp-arg": {"type": "append", "help": "Add custom mpp arg"},
    "--cache": {"type": "str", "help": "Add mpp cache-directory to use"},
    "--define": {
        "type": "append",
        "help": "Define key=yaml-value",
    },
    "--define-file": {
        "type": "append",
        "help": "Add yaml file of defines",
    },
    "--extend-define": {
        "type": "append",
        "help": "Extend array by item or list key=yaml-value",
    },
    "--dump-variables": "Dump variables that would be used when building and exit.",
}

# Full arguments for formating mpp files
FORMAT_ARGS = {
    "--target": {
        "type": "str",
        "default": "qemu",
        "help": "Build for this target",
    },
    "--mode": {
        "type": "str",
        "default": "image",
        "help": "Build this image mode (package, image)",
    },
    "--policy": {
        "type": "str",
        "help": "Path to policy file (.aibp.yml) for build restrictions",
        "exclusive-group": "policy",
    },
    "--fusa": {
        "help": "Use built-in FUSA compliance policy (equivalent to --policy fusa.aibp.yml)",
        "exclusive-group": "policy",
    },
    "--ostree-repo": {"type": "str", "help": "Path to ostree repo"},
}

# Base arguments for building, doesn't include options not used by build-bootc-builder
SHARED_BUILD_ARGS = {
    "--osbuild-manifest": {
        "type": "str",
        "help": "Path to store osbuild manifest",
    },
    "--cache-max-size": {
        "type": "str",
        # We set the default size to 2GB, which allows about two copies of the build pipeline.
        "default": "2GB",
        "help": "Max cache size",
    },
    "--build-dir": {
        "type": "str",
        "default": os.getenv("OSBUILD_BUILDDIR"),
        "help": "Directory where intermediary files are stored)",
    },
    "--progress": {
        "type": "bool-optional",
        "help": "Disable progress bar",
        "default": sys.stdout.isatty(),
    },
}

subcommands = [
    ["list-dist", "list available distributions", list_dist, LIST_ARGS],
    ["list-targets", "list available targets", list_targets, LIST_ARGS],
    ["list-exports", "list available exports", list_exports, LIST_ARGS],
    [
        "compose",
        "Compose osbuild manifest",
        compose,
        SHARED_FORMAT_ARGS,
        FORMAT_ARGS,
        {
            "manifest": "Source manifest file",
            "out": "Output osbuild json",
        },
    ],
    [
        "list-rpms",
        "List rpms",
        listrpms,
        SHARED_FORMAT_ARGS,
        FORMAT_ARGS,
        {
            "manifest": "Source manifest file",
        },
    ],
    [
        "build",
        "Compose and build osbuild manifest",
        build,
        SHARED_FORMAT_ARGS,
        FORMAT_ARGS,
        SHARED_BUILD_ARGS,
        {
            "--export": {
                "type": "append",
                "help": "Export this image type",
                "required": True,
            },
            "manifest": "Source manifest file",
            "out": "Output path",
        },
    ],
    [
        "build-bootc-builder",
        "Create container image to build physical bootc images",
        build_bootc_builder,
        SHARED_FORMAT_ARGS,
        SHARED_BUILD_ARGS,
        {
            "out": "Name of container image to build",
        },
    ],
    [
        "bootc-to-disk-image",
        "Create disk image from bootc container",
        bootc_to_disk_image,
        {
            "--bib-container": {
                "type": "str",
                "default": default_bib_container,
                "help": "bootc-image builder-container image to use",
            },
            "--build-container": {
                "type": "str",
                "help": "bootc build container image to use",
            },
            "src_container": "Bootc container name",
            "out": "Output image name",
        },
    ],
    [
        "bootc-extract-for-signing",
        "Extract file that need signing",
        bootc_extract_for_signing,
        {
            "src_container": "Bootc container name",
            "out": "Output directory",
        },
    ],
    [
        "bootc-inject-signed",
        "Inject signed files",
        bootc_inject_signed,
        {
            "src_container": "Bootc container name",
            "srcdir": "Directory with signed files",
            "new_container": "Destination container name",
        },
    ],
]


def main():
    args = AIBParameters(args=parse_args(sys.argv[2:], base_dir), base_dir=base_dir)

    if args.verbose:
        log.setLevel("DEBUG")

    runner = Runner(args)
    runner.add_volume(os.getcwd())

    with tempfile.TemporaryDirectory(
        prefix="automotive-image-builder-", dir="/var/tmp"
    ) as tmpdir:
        runner.add_volume(tmpdir)
        try:
            return args.func(tmpdir, runner)
        except KeyboardInterrupt:
            log.info("Build interrupted by user")
            sys.exit(130)
        except (exceptions.AIBException, FileNotFoundError) as e:
            log.error("%s", e)
            sys.exit(1)
        except Exception:
            log.error("Unexpected exception occurred!")
            raise


if __name__ == "__main__":
    sys.exit(main())
