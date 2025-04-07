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

from .utils import yaml_load_ordered, extract_comment_header, get_osbuild_major_version
from .exports import export, EXPORT_DATAS, get_export_data
from .runner import Runner
from .ostree import OSTree
from .simple import ManifestLoader
from .version import __version__
from . import exceptions
from . import AIBParameters
from . import log
from . import vmhelper


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
        v = yaml_load_ordered(yaml_v)
    except yaml.parser.ParserError as e:
        raise exceptions.InvalidOption(option, yaml_v) from e
    return k, v


def parse_args(args, base_dir):
    isRoot = os.getuid() == 0
    parser = argparse.ArgumentParser(
        prog="automotive-image-builder", description="Build automotive images"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--verbose", default=False, action="store_true")
    parser.add_argument(
        "--container",
        default=False,
        action="store_true",
        help="Use containerized build",
    )
    container_image_name_default = (
        "quay.io/centos-sig-automotive/automotive-image-builder"
    )
    parser.add_argument(
        "--container-image-name",
        action="store",
        type=str,
        default=container_image_name_default,
        help=f"Container image name, {container_image_name_default} is "
        "default if this option remains unused",
    )
    parser.add_argument(
        "--container-autoupdate",
        default=False,
        action="store_true",
        help="Automatically pull new container image if available",
    )
    parser.add_argument(
        "--include",
        action="append",
        type=str,
        default=[],
        help="Add include directory",
    )
    parser.add_argument("--vm", default=False, action="store_true")
    parser.set_defaults(func=no_subcommand)
    subparsers = parser.add_subparsers(help="sub-command help")

    parser_list_dist = subparsers.add_parser(
        "list-dist", help="list available distributions"
    )
    parser_list_dist.set_defaults(func=list_dist)
    parser_list_dist.add_argument("--quiet", default=False, action="store_true")

    parser_list_target = subparsers.add_parser(
        "list-targets", help="list available targets"
    )
    parser_list_target.set_defaults(func=list_targets)
    parser_list_target.add_argument("--quiet", default=False, action="store_true")

    parser_list_export = subparsers.add_parser(
        "list-exports", help="list available exports"
    )
    parser_list_export.set_defaults(func=list_exports)
    parser_list_export.add_argument("--quiet", default=False, action="store_true")

    format_parser = argparse.ArgumentParser(add_help=False)
    format_parser.add_argument(
        "--arch",
        default=platform.machine(),
        action="store",
        help=f"Arch to run for (default {platform.machine()})",
    )
    format_parser.add_argument(
        "--osbuild-mpp",
        action="store",
        type=str,
        default=os.path.join(base_dir, "mpp/aib-osbuild-mpp"),
        help="Use this osbuild-mpp binary",
    )
    format_parser.add_argument(
        "--target",
        action="store",
        type=str,
        default="qemu",
        help="Build for this target",
    )
    format_parser.add_argument(
        "--mode",
        action="store",
        type=str,
        default="image",
        help="Build this image mode (package, image)",
    )
    format_parser.add_argument(
        "--distro",
        action="store",
        type=str,
        default="autosd9-sig",
        help="Build for this distro specification",
    )
    format_parser.add_argument(
        "--mpp-arg",
        action="append",
        type=str,
        default=[],
        help="Add custom mpp arg",
    )
    format_parser.add_argument(
        "--cache",
        action="store",
        type=str,
        help="Add mpp cache-directory to use",
    )
    format_parser.add_argument(
        "--fusa",
        action="store_true",
        default=False,
        help="Enable required options for functional safety",
    )
    format_parser.add_argument(
        "--define",
        action="append",
        type=str,
        default=[],
        help="Define key=yaml-value",
    )
    format_parser.add_argument(
        "--define-file",
        action="append",
        type=str,
        default=[],
        help="Add yaml file of defines",
    )
    format_parser.add_argument(
        "--extend-define",
        action="append",
        type=str,
        default=[],
        help="Extend array by item or list key=yaml-value",
    )
    format_parser.add_argument(
        "--ostree-repo", action="store", type=str, help="Path to ostree repo"
    )
    format_parser.add_argument(
        "--dump-variables",
        default=False,
        action="store_true",
        help="Dump variables that would be used when building and exit.",
    )

    parser_compose = subparsers.add_parser(
        "compose", help="Compose osbuild manifest", parents=[format_parser]
    )
    parser_compose.add_argument("manifest", type=str, help="Source manifest file")
    parser_compose.add_argument("out", type=str, help="Output osbuild json")
    parser_compose.set_defaults(func=compose)

    parser_listrpms = subparsers.add_parser(
        "list-rpms", help="List rpms", parents=[format_parser]
    )
    parser_listrpms.add_argument("manifest", type=str, help="Source manifest file")
    parser_listrpms.set_defaults(func=listrpms)

    parser_build = subparsers.add_parser(
        "build", help="Compose and build osbuild manifest", parents=[format_parser]
    )
    parser_build.add_argument(
        "--osbuild-manifest",
        action="store",
        type=str,
        help="Path to store osbuild manifest",
    )
    parser_build.add_argument(
        # We set the default size to 2GB, which allows about two copies
        # of the build pipeline.
        "--cache-max-size",
        action="store",
        default="2GB",
        type=str,
        help="Max cache size",
    )
    parser_build.add_argument(
        "--export",
        action="append",
        type=str,
        default=[],
        help="Export this image type",
        required=True,
    )
    parser_build.add_argument(
        "--build-dir",
        action="store",
        type=str,
        default=os.getenv("OSBUILD_BUILDDIR"),
        help="Directory where intermediary files are stored)",
    )
    parser_build.add_argument(
        "--sudo",
        default=not isRoot,
        action="store_true",
        help="Use sudo to start programs that need privileges "
        "(default if not run as root)",
    )
    parser_build.add_argument(
        "--nosudo",
        default=False,
        action="store_true",
        help="Don't use sudo to start programs",
    )

    parser_build.add_argument("manifest", type=str, help="Source manifest file")
    parser_build.add_argument("out", type=str, help="Output path")
    parser_build.set_defaults(func=build)

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
        "_workdir": tmpdir,
        "name": manifest.get("mpp-vars", {}).get(
            "name", strip_ext(os.path.basename(args.manifest))
        ),
        "arch": args.arch,
        "target": args.target,
        "distro_name": args.distro,
        "image_mode": args.mode,
        "use_fusa": args.fusa,
        "osbuild_major_version": get_osbuild_major_version(
            runner, use_container=(args.vm or args.container)
        ),
        # This is a leftover for backwards compatibilty:
        "image_type": "ostree" if args.mode == "image" else "regular",
    }

    if args.dump_variables:
        defines["print_variables"] = True

    defines["exports"] = args.export if args.export else []

    if args.simple_manifest:
        loader = ManifestLoader(defines)

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
                file_defines = yaml_load_ordered(f)
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

    runner.run(
        cmdline,
        use_sudo=True,
        use_container=True,
        use_non_root_user_in_container=True,
    )


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
    if args.nosudo:
        args.sudo = False

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
        runner.run(cmdline, use_sudo=True, use_container=True)

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

        runner.run(["tar", "xvf", output_tar, "-C", outputdir], use_sudo=True)
    else:
        for exp in exports:
            cmdline += ["--export", exp]

        cmdline += [osbuild_manifest]

        runner.run(cmdline, use_sudo=True, use_container=True)

    if args.ostree_repo:
        repodir = os.path.join(outputdir, "ostree-commit/repo")
        runner.run(
            ["ostree", "pull-local", "--repo=" + args.ostree_repo, repodir],
            use_container=True,
        )

    if len(args.export) == 1:
        # Export directly to args.out
        export(outputdir, args.out, False, args.export[0], runner)
    else:
        if os.path.isdir(args.out) or os.path.isfile(args.out):
            runner.run(["rm", "-rf", args.out], use_sudo=True)
        os.mkdir(args.out)
        for exp in args.export:
            export(outputdir, args.out, True, exp, runner)

    runner.run(["rm", "-rf", outputdir], use_sudo=True)


def build(args, tmpdir, runner):
    try:
        _build(args, tmpdir, runner)
    finally:

        # Ensure we can clean up these directories, that can have
        # weird permissions
        if args.sudo and (
            os.path.isdir(os.path.join(tmpdir, "osbuild_store"))
            or os.path.isdir(os.path.join(tmpdir, "image_output"))
        ):
            runner.run(["rm", "-rf", tmpdir], use_sudo=True)


def no_subcommand(_args, _tmpdir, _runner):
    log.info("No subcommand specified, see --help for usage")


def main():
    base_dir = os.path.realpath(sys.argv[1])
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
        except (exceptions.AIBException, FileNotFoundError) as e:
            log.error("%s", e)
            sys.exit(1)
        except Exception:
            log.error("Unexpected exception occurred!")
            raise


if __name__ == "__main__":
    sys.exit(main())
