#!/usr/bin/env python3

import argparse
import base64
import collections
import sys
import os
import platform
import json
import subprocess
import yaml

from .utils import (
    extract_comment_header,
    get_osbuild_major_version,
    read_public_key,
    read_keys,
    generate_keys,
    DiskFormat,
)
from .exports import export, get_export_data
from .runner import Runner
from .ostree import OSTree
from .simple import ManifestLoader
from .utils import SudoTemporaryDirectory, extract_part_of_file
from .version import __version__
from . import exceptions
from . import AIBParameters
from . import log
from . import vmhelper
from .podman import (
    podman_image_exists,
    podman_image_info,
    podman_run_bootc_image_builder,
    podman_bootc_inject_pubkey,
    PodmanImageMount,
)

default_distro = "autosd10-sig"
default_container_image_name = "quay.io/centos-sig-automotive/automotive-image-builder"
base_dir = os.path.realpath(sys.argv[1])
default_bib_container = "quay.io/centos-bootc/bootc-image-builder:latest"


def aib_build_container_name(distro):
    return f"localhost/aib-build:{distro}"


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


def list_distro(args, _tmpdir, _runner):
    list_ipp_items(args, "distro")


def list_targets(args, _tmpdir, _runner):
    list_ipp_items(args, "targets")


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
        errors = []

        # Validate manifest type
        errors.extend(
            args.policy.validate_manifest_type(args.simple_manifest is not None)
        )

        # Validate build arguments
        errors.extend(
            args.policy.validate_build_args(
                args.mode, args.target, args.distro, args.arch
            )
        )

        if errors:
            raise exceptions.AIBException(
                "Policy validation failed:\n" + "\n".join(errors)
            )


def create_osbuild_manifest(args, tmpdir, out, runner, exports):
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
        "_workdir": tmpdir.name,
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

    defines["exports"] = exports

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

    cmdline = [os.path.join(base_dir, "mpp/aib-osbuild-mpp")]
    for inc in args.include_dirs:
        cmdline += ["-I", inc]

    for k in sorted(defines.keys()):
        v = defines[k]
        cmdline += ["-D", f"{k}={json.dumps(v)}"]

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

    create_osbuild_manifest(args, tmpdir, osbuild_manifest, runner, args.exports)

    data = extract_rpmlist_json(osbuild_manifest)

    print(data)


def _run_osbuild(args, tmpdir, runner, exports):
    if args.out:
        runner.add_volume_for(args.out)

    osbuild_manifest = os.path.join(tmpdir, "osbuild.json")
    if args.osbuild_manifest:
        osbuild_manifest = args.osbuild_manifest

    create_osbuild_manifest(args, tmpdir, osbuild_manifest, runner, exports)

    builddir = tmpdir
    if args.build_dir:
        builddir = args.build_dir
        os.makedirs(builddir, exist_ok=True)
    runner.add_volume(builddir)
    runner.add_volume("/dev")

    cmdline = ["osbuild"]

    with SudoTemporaryDirectory(prefix="image_output--", dir=builddir) as outputdir:
        cmdline += [
            "--store",
            os.path.join(builddir, "osbuild_store"),
            "--output-directory",
            outputdir.name,
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

        if args.vm:
            # Download sources on host, using no exports

            cmdline += [osbuild_manifest]
            runner.run_in_container(
                cmdline,
                progress=args.progress,
                verbose=args.verbose,
                log_file=args.log_file(tmpdir),
            )

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
                vmhelper.get_container(
                    container_file, args.arch, args.container_image_name
                )

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

            runner.run_as_root(["tar", "xvf", output_tar, "-C", outputdir.name])
        else:
            for exp in exports:
                cmdline += ["--export", exp]

            cmdline += [osbuild_manifest]

            runner.run_in_container(
                cmdline,
                need_osbuild_privs=True,
                progress=args.progress,
                verbose=args.verbose,
                log_file=args.log_file(tmpdir),
            )

        return outputdir.detach()


def build(args, tmpdir, runner):
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

    with _run_osbuild(args, tmpdir, runner, exports) as outputdir:
        if args.ostree_repo:
            repodir = os.path.join(outputdir.name, "ostree-commit/repo")
            runner.run_as_user(
                ["ostree", "pull-local", "--repo=" + args.ostree_repo, repodir]
            )

        if len(args.export) == 0:
            pass
        elif len(args.export) == 1:
            # Export directly to args.out
            export(outputdir.name, args.out, False, args.export[0], runner)
        else:
            if os.path.isdir(args.out) or os.path.isfile(args.out):
                runner.run_as_root(["rm", "-rf", args.out])
            os.mkdir(args.out)
            for exp in args.export:
                export(outputdir.name, args.out, True, exp, runner)


def bootc_archive_to_store(runner, archive_file, container_name, user=False):
    cmdline = [
        "skopeo",
        "copy",
        "--quiet",
        "oci-archive:" + archive_file,
        "containers-storage:" + container_name,
    ]

    if user:
        subprocess.run(cmdline)
    else:
        runner.run_as_root(cmdline)


def build_bootc(args, tmpdir, runner):
    args.mode = "image"

    exports = []
    if not args.dry_run:
        exports.append("bootc-tar" if args.tar else "bootc-archive")

    with _run_osbuild(args, tmpdir, runner, exports) as outputdir:
        if args.tar:
            output_file = os.path.join(outputdir.name, "bootc-tar/rootfs.tar")
        else:
            output_file = os.path.join(
                outputdir.name, "bootc-archive/image.oci-archive"
            )

        if args.dry_run:
            pass
        elif args.tar or args.oci_archive:
            runner.run_as_root(["chown", f"{os.getuid()}:{os.getgid()}", output_file])
            runner.run_as_root(["mv", output_file, args.out])
        else:
            bootc_archive_to_store(runner, output_file, args.out, user=args.user)


def convert_image_file(runner, src, dest, fmt):
    runner.run_in_container(fmt.convert + [src, dest])
    runner.run_as_root(["chown", f"{os.getuid()}:{os.getgid()}", dest])


def export_disk_image_file(runner, args, tmpdir, image_file, fmt):
    if args.separate_partitions:
        runner.run_as_root(["rm", "-rf", args.out])
        os.mkdir(args.out)

        disk_json = runner.run_in_container(
            ["sfdisk", "--json", image_file], capture_output=True
        )
        parts = json.loads(disk_json)
        for idx, p in enumerate(parts["partitiontable"]["partitions"]):
            start = int(p["start"]) * 512
            size = int(p["size"]) * 512
            name = p.get("name", f"part{idx}")

            part_tmp_file = os.path.join(tmpdir, "part.img")
            part_file = os.path.join(args.out, name + "." + fmt)
            extract_part_of_file(image_file, part_tmp_file, start, size)
            convert_image_file(runner, part_tmp_file, part_file, fmt)
    else:
        convert_image_file(runner, image_file, args.out, fmt)


def build_traditional(args, tmpdir, runner):
    use_ostree = args.ostree or args.ostree_repo
    args.mode = "image" if use_ostree else "package"

    fmt = DiskFormat.from_string(args.format) or DiskFormat.from_filename(args.out)

    exports = []
    if not args.dry_run:
        exports.append("image")
        if args.ostree_repo:
            exports.append("ostree-commit")

    with _run_osbuild(args, tmpdir, runner, exports) as outputdir:
        output_file = os.path.join(outputdir.name, "image/disk.img")

        if not args.dry_run:
            export_disk_image_file(runner, args, tmpdir, output_file, fmt)


def download(args, tmpdir, runner):
    if not args.build_dir:
        log.error("No build dir specified, refusing to download to temporary directory")
        sys.exit(1)
    args.out = None
    args.mode = "image"
    exports = []

    outputdir = _run_osbuild(args, tmpdir, runner, exports)
    outputdir.cleanup()


def build_bootc_builder(args, tmpdir, runner):
    # build-bootc-builder is a special form of the "build" command with fixed values for
    # manifest/export/target/mode arguments.
    args.simple_manifest = os.path.join(args.base_dir, "files/bootc-builder.aib.yml")
    args.manifest = os.path.join(args.base_dir, "files/simple.mpp.yml")
    args.target = "qemu"
    args.mode = "image"

    dest_image = args.out or aib_build_container_name(args.distro)

    with _run_osbuild(args, tmpdir, runner, ["bootc-archive"]) as outputdir:
        output_file = os.path.join(outputdir.name, "bootc-archive/image.oci-archive")

        bootc_archive_to_store(runner, output_file, dest_image)

        print(f"Built image {dest_image}")


def get_build_container_for(container):
    info = podman_image_info(container)
    if not info:
        log.error("'%s' not found in local container store", container)
        sys.exit(1)

    # Use same distro for build image as the source container image
    distro = default_distro
    if info.build_info:
        distro = info.build_info.get("DISTRO", distro)

    build_container = aib_build_container_name(distro)
    if not podman_image_exists(build_container):
        log.error("Build container %s isn't in local container store", build_container)
        log.error(
            "Either specify another one with --build-container, or create it using: "
        )
        log.error(
            " automotive-image-builder build-bootc-builder --distro %s",
            distro,
        )
        sys.exit(1)
    return build_container


def bootc_to_disk_image(args, tmpdir, runner):
    if not podman_image_exists(args.src_container):
        log.error(
            "Source bootc image '%s' isn't in local container store", args.src_container
        )
        sys.exit(1)

    fmt = DiskFormat.from_string(args.format) or DiskFormat.from_filename(args.out)

    with SudoTemporaryDirectory(
        prefix="bib-out--", dir=os.path.dirname(args.out)
    ) as outputdir:
        output_file = os.path.join(outputdir.name, "image.raw")

        res = podman_run_bootc_image_builder(
            args.bib_container,
            args.build_container or get_build_container_for(args.src_container),
            args.src_container,
            "raw",
            output_file,
            args.verbose,
        )
        if res != 0:
            log.error("bootc-image-builder failed to create the image")
            sys.exit(1)

        export_disk_image_file(runner, args, tmpdir, output_file, fmt)


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


def bootc_reseal(args, tmpdir, runner):
    if not podman_image_exists(args.src_container):
        log.error(
            "Source bootc image '%s' isn't in local container store", args.src_container
        )
        sys.exit(1)

    if args.key:
        (pubkey, privkey) = read_keys(args.key, args.passwd)
        src_container = args.src_container
    else:
        (pubkey, privkey) = generate_keys()

        pubkey_file = os.path.join(tmpdir, "pubkey")
        with open(pubkey_file, "w", encoding="utf8") as f:
            f.write(pubkey)

        build_container = args.build_container
        if not build_container:
            build_container = get_build_container_for(args.src_container)

        src_container = podman_bootc_inject_pubkey(
            args.src_container, None, pubkey_file, build_container, args.verbose
        )

    privkey_file = os.path.join(tmpdir, "pkey")
    with os.fdopen(
        os.open(privkey_file, os.O_CREAT | os.O_WRONLY, mode=0o600), "w"
    ) as f:
        f.write(privkey)

    runner.run_in_container(
        [
            "rpm-ostree",
            "experimental",
            "compose",
            "build-chunked-oci",
            "--sign-commit",
            f"ed25519={privkey_file}",
            "--bootc",
            "--format-version=1",
            f"--from={src_container}",
            f"--output=containers-storage:{args.new_container}",
        ],
        stdout_to_devnull=not args.verbose,
    )


def bootc_prepare_reseal(args, tmpdir, runner):
    if not podman_image_exists(args.src_container):
        log.error(
            "Source bootc image '%s' isn't in local container store", args.src_container
        )
        sys.exit(1)

    build_container = args.build_container
    if not build_container:
        build_container = get_build_container_for(args.src_container)

    pubkey = read_public_key(args.key, args.passwd)
    pubkey_file = os.path.join(tmpdir, "pubkey")

    with open(pubkey_file, "w", encoding="utf8") as f:
        f.write(pubkey)

    podman_bootc_inject_pubkey(
        args.src_container,
        args.new_container,
        pubkey_file,
        build_container,
        args.verbose,
    )


def no_subcommand(_args, _tmpdir, _runner):
    log.info("No subcommand specified, see --help for usage")


def add_arg(parser, groups, name, data, suppress_default=False, suppress_help=False):
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
    for name, data in args.items():
        add_arg(
            parser,
            groups,
            name,
            data,
            suppress_default=suppress_default,
            suppress_help=suppress_help,
        )


class AIBHelpFormatter(argparse.RawDescriptionHelpFormatter):
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


def parse_args(args, base_dir):
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
    parser.set_defaults(func=no_subcommand)

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
    "vm": {
        "--vm": {"help": "Build in a virtual machine"},
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
        "default": "qemu",
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
        # We set the default size to 2GB, which allows about two copies of the build pipeline.
        "default": "2GB",
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
        "help": "Define internal varible key to a specified value",
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

build_subcommands = [
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
        build_bootc,
        ["container", "include", "vm"],
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
        build_traditional,
        ["container", "include", "vm"],
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
        "source. The tools neet to that match the version of the image, so these\n"
        "containers are built for specific distro versions.\n"
        "\n"
        "The container to use in bootc-to-disk-iamge can be specified with --build-container,\n"
        "but normally the default name of 'localhost/aib-build:$DISTRO' is used, and if\n"
        "the out argument is not specified this will be used.\n",
        build_bootc_builder,
        ["container", "include", "vm"],
        BUILD_ARGS,
        {"out": {"help": "Name of container image to build", "required": False}},
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
        build,
        ["container", "include", "vm"],
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
                "required": True,
            },
            "manifest": "Source manifest file",
            "out": "Output path",
        },
        POLICY_ARGS,
        TARGET_ARGS,
        BUILD_ARGS,
    ],
]

bootc_subcommands = [
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
        bootc_to_disk_image,
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
        bootc_extract_for_signing,
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
        bootc_inject_signed,
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
        bootc_reseal,
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
        bootc_prepare_reseal,
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

subcommands = [
    [
        "list-distro",
        "list available distributions",
        "List all the available distributions available for --distro.",
        list_distro,
        ["include"],
        LIST_ARGS,
    ],
    [
        "list-targets",
        "list available targets",
        "List all the available targets available for --target.",
        list_targets,
        ["include"],
        LIST_ARGS,
    ],
    [
        "list-rpms",
        "List the rpms that a manifest would use when built",
        "List the rpms that a manifest would use when build",
        listrpms,
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
        download,
        [],
        TARGET_ARGS,
        BUILD_ARGS,
        {
            "manifest": "Source manifest file",
        },
    ],
]

subcommand_groups = [
    ["Basic image building", build_subcommands],
    ["Bootc operations", bootc_subcommands],
    ["Other commands", subcommands],
]


def main():
    args = AIBParameters(args=parse_args(sys.argv[2:], base_dir), base_dir=base_dir)

    if args.verbose:
        log.setLevel("DEBUG")

    runner = Runner(args)
    runner.add_volume(os.getcwd())

    with SudoTemporaryDirectory(
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
