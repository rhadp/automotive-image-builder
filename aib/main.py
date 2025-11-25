#!/usr/bin/env python3

import base64
import sys
import os
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
from .utils import SudoTemporaryDirectory, extract_part_of_file, rm_rf
from . import exceptions
from . import AIBParameters
from . import log
from .podman import (
    podman_image_exists,
    podman_image_info,
    podman_run_bootc_image_builder,
    podman_bootc_inject_pubkey,
    PodmanImageMount,
)
from .arguments import parse_args, default_distro, aib_build_container_name

base_dir = os.path.realpath(sys.argv[1])
default_target = "qemu"


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


def validate_policy_args(args, target):
    """Validate build arguments against policy restrictions."""
    if args.policy:
        errors = []

        # Validate manifest type
        errors.extend(
            args.policy.validate_manifest_type(args.simple_manifest is not None)
        )

        # Validate build arguments
        errors.extend(
            args.policy.validate_build_args(args.mode, target, args.distro, args.arch)
        )

        if errors:
            raise exceptions.AIBException(
                "Policy validation failed:\n" + "\n".join(errors)
            )


def create_osbuild_manifest(args, tmpdir, out, runner):
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
        "distro_name": args.distro,
        "image_mode": args.mode,
        "osbuild_major_version": get_osbuild_major_version(
            runner, use_container=args.container
        ),
        # This is a leftover for backwards compatibilty:
        "image_type": "ostree" if args.mode == "image" else "regular",
    }

    if args.dump_variables:
        defines["print_variables"] = True

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

    defines["target"] = default_target
    if args.simple_manifest:
        loader = ManifestLoader(defines, args.policy)

        # Note: This may override the 'target' define
        loader.load(args.simple_manifest, os.path.dirname(args.simple_manifest))
    if args.target:
        defines["target"] = args.target

    validate_policy_args(args, defines["target"])

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

    create_osbuild_manifest(args, tmpdir, osbuild_manifest, runner)

    data = extract_rpmlist_json(osbuild_manifest)

    print(data)


def _run_osbuild(args, tmpdir, runner, exports):
    if args.out:
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
                "extra-tree-content",
                "--checkpoint",
                "qm_rootfs_base",
                "--checkpoint",
                "qm_rootfs",
                "--checkpoint",
                "data",
                "--checkpoint",
                "rootfs",
            ]

        if args.cache_max_size:
            cmdline += ["--cache-max-size=" + args.cache_max_size]

        if args.progress:
            # Add JSONSeqMonitor for progress monitoring
            cmdline += ["--monitor", "JSONSeqMonitor"]

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

    is_bootc = False
    # Rewrite exports according to export_data
    for exp in args.export:
        if "bootc" in exp:
            is_bootc = True
        data = get_export_data(exp)
        exp = data.get("export_arg", exp)
        exports.append(exp)
        if exp == "ostree-commit":
            has_repo = True

    # Rewrite --mode image and --export bootc... to mode=bootc
    if is_bootc:
        if args.mode != "image":
            raise exceptions.AIBException(f"mode {args.mode} not compabible with bootc")
        args.mode = "bootc"

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
    args.mode = "bootc"

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


def partition_is_safe_to_truncate(p):
    name = p.get("name")
    if name:
        prefixes = ["boot_", "vbmeta_", "ukiboot"]
        for p in prefixes:
            if name.startswith(p):
                return True
    return False


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
            part_file = os.path.join(args.out, name + fmt.ext)
            extract_part_of_file(
                image_file,
                part_tmp_file,
                start,
                size,
                skip_zero_tail=partition_is_safe_to_truncate(p),
            )
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
    args.mode = "bootc"

    dest_image = args.out or aib_build_container_name(args.distro)

    if args.if_needed:
        info = podman_image_info(dest_image)
        if info:
            print(f"Image {dest_image} already exists, doing nothing.")
            return

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
    rm_rf(args.out)
    os.makedirs(args.out)
    with PodmanImageMount(args.src_container) as mount:
        if mount.has_file("/etc/signing_info.json"):
            content = mount.read_file("/etc/signing_info.json")
            info = json.loads(content)

            with open(os.path.join(args.out, "signing_info.json"), "w") as f:
                f.write(content)
            for f in info.get("signed_files", []):
                _type = f["type"]
                filename = f["filename"]
                src = f["paths"][0]  # All files should be the same, copy out first

                if _type == "efi":
                    destdir = os.path.join(args.out, "efi")
                elif _type in ["aboot", "vbmeta"]:
                    destdir = os.path.join(args.out, "aboot")
                else:
                    log.error(f"Unknown signature type {_type}")
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
                elif _type in ["aboot", "vbmeta"]:
                    srcdir = os.path.join(args.srcdir, "aboot")
                else:
                    log.error(f"Unknown signature type {_type}")
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


def main():
    callbacks = {
        "build_bootc": build_bootc,
        "build_traditional": build_traditional,
        "build_bootc_builder": build_bootc_builder,
        "build": build,
        "bootc_to_disk_image": bootc_to_disk_image,
        "bootc_extract_for_signing": bootc_extract_for_signing,
        "bootc_inject_signed": bootc_inject_signed,
        "bootc_reseal": bootc_reseal,
        "bootc_prepare_reseal": bootc_prepare_reseal,
        "list_distro": list_distro,
        "list_targets": list_targets,
        "listrpms": listrpms,
        "download": download,
        "no_subcommand": no_subcommand,
    }

    args = AIBParameters(
        args=parse_args(sys.argv[2:], base_dir, callbacks), base_dir=base_dir
    )

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
