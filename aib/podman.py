import os
import shlex
import subprocess
import shutil
import tempfile

from . import log


def sudo_cmd(args, capture_output=False):
    allowed_env_vars = [
        "REGISTRY_AUTH_FILE",
        "CONTAINERS_CONF",
        "CONTAINERS_REGISTRIES_CONF",
        "CONTAINERS_STORAGE_CONF",
    ]
    cmdline = [
        "sudo",
        "--preserve-env={}".format(",".join(allowed_env_vars)),
    ] + args

    log.debug("Running: %s", shlex.join(cmdline))

    r = subprocess.run(cmdline, capture_output=capture_output)
    if capture_output:
        if r.returncode != 0:
            raise Exception(
                f"Failed to run '{shlex.join(args)}': "
                + r.stderr.decode("utf-8").rstrip()
            )
        return r.stdout.decode("utf-8").rstrip()
    return r.returncode


def podman_image_exists(image):
    return sudo_cmd(["podman", "image", "exists", image]) == 0


def podman_image_read_file(image, path):
    image_path = sudo_cmd(["podman", "image", "mount", image], True).strip()
    try:
        file_path = os.path.join(image_path, os.path.splitroot(path)[2])
        content = sudo_cmd(["cat", file_path], True)
    finally:
        sudo_cmd(["podman", "image", "unmount", image])
    return content


def parse_shvars(content):
    result = {}
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for tok in shlex.split(line):
            if "=" in tok:
                k, v = tok.split("=", 1)
                result[k] = v
    return result


class ContainerInfo:
    def __init__(self, name, build_info):
        self.name = name
        self.build_info = build_info

    def __str__(self):
        return f"{self.name}({self.build_info})"


def podman_image_info(image):
    if not podman_image_exists(image):
        return None
    build_info = None
    try:
        content = podman_image_read_file(image, "/etc/build-info")
        build_info = parse_shvars(content)
    except Exception as e:
        log.info("No build info in %s: %s", image, e)
    return ContainerInfo(image, build_info)


def podman_run_bootc_image_builder(
    bib_container, build_container, bootc_container, build_type, dest_path
):
    if build_type == "raw":
        src_path = "image/disk.raw"
    elif build_type == "qcow2":
        src_path = "qcow2/disk.qcow2"
    elif build_type == "vmdk":
        src_path = "vmdk/disk.vmdk"
    elif build_type == "vpc":
        src_path = "vpc/disk.vpc"
    elif build_type == "ovf":
        src_path = "ovf/disk.ovf"
    else:
        raise Exception(f"Unknown bootc-image-builder type {build_type}")

    with tempfile.TemporaryDirectory(
        prefix="automotive-image-builder-", dir="/var/tmp"
    ) as tmpdir:
        try:
            cmdline = [
                "podman",
                "run",
                "--rm",
                "-it",
                "--privileged",
                "--security-opt",
                "label=type:unconfined_t",
                "-v",
                tmpdir + ":/output",
                "-v",
                "/var/lib/containers/storage:/var/lib/containers/storage",
                bib_container,
                "--build-container",
                build_container,
                "--progress",
                "verbose",
                "--type",
                build_type,
                bootc_container,
            ]
            res = sudo_cmd(cmdline)

            if res == 0:
                src = os.path.join(tmpdir, src_path)
                log.debug("Copying: %s to %s", src, dest_path)
                shutil.copyfile(src, dest_path, follow_symlinks=False)
            return res

        finally:
            # Need sudo to have permissions to clean up the tmpdir
            sudo_cmd(["rm", "-rf", tmpdir])
