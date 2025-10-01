import os
import shlex
import subprocess
import shutil
import tempfile

from . import log


def run_cmd(
    args,
    capture_output=False,
    with_sudo=True,
    return_pipe=False,
    stdin_pipe=None,
    stdout_pipe=None,
):
    allowed_env_vars = [
        "REGISTRY_AUTH_FILE",
        "CONTAINERS_CONF",
        "CONTAINERS_REGISTRIES_CONF",
        "CONTAINERS_STORAGE_CONF",
    ]

    if with_sudo:
        cmdline = [
            "sudo",
            "--preserve-env={}".format(",".join(allowed_env_vars)),
        ] + args
    else:
        cmdline = args

    log.debug("Running: %s", shlex.join(cmdline))

    if return_pipe:
        # Return stdout pipe for streaming
        process = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stdin=stdin_pipe)
        return process.stdout

    if capture_output:
        r = subprocess.run(cmdline, capture_output=True, stdin=stdin_pipe)
    else:
        r = subprocess.run(cmdline, stdin=stdin_pipe, stdout=stdout_pipe)
    if capture_output:
        if r.returncode != 0:
            raise Exception(
                f"Failed to run '{shlex.join(args)}': "
                + r.stderr.decode("utf-8").rstrip()
            )
        return r.stdout.decode("utf-8").rstrip()
    return r.returncode


class PodmanImageMount:
    """Context manager for mounting and unmounting podman images."""

    def __init__(self, image, with_sudo=True, writable=False, commit_image=None):
        self.image = image
        self.mount_path = None
        self.with_sudo = with_sudo
        self.writable = writable
        self.commit_image = commit_image
        self.container_id = None

    def __enter__(self):
        if self.writable:
            # Create a container from the image
            self.container_id = self.capture(["podman", "create", self.image]).strip()
            # Mount the container
            self.mount_path = self.capture(
                ["podman", "mount", self.container_id]
            ).strip()
        else:
            # Mount the image directly (read-only)
            self.mount_path = self.capture(
                ["podman", "image", "mount", self.image]
            ).strip()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.mount_path:
            if self.writable and self.container_id:
                # Unmount the container
                self.capture(["podman", "unmount", self.container_id])
                # Commit the container to a new image if requested
                if self.commit_image:
                    self.run(["podman", "commit", self.container_id, self.commit_image])
                # Remove the container
                self.capture(["podman", "rm", self.container_id])
            else:
                # Unmount the image
                self.capture(["podman", "image", "unmount", self.image])

    def _ensure_mounted(self):
        """Ensure the image is mounted, raise RuntimeError if not."""
        if not self.mount_path:
            raise RuntimeError("Image not mounted - use within 'with' statement")

    def _get_full_path(self, path):
        """Convert a path to a full path within the mounted image."""
        return os.path.join(self.mount_path, os.path.splitroot(path)[2])

    def run(self, cmd, stdin_pipe=None, stdout_pipe=None):
        return run_cmd(
            cmd,
            False,
            with_sudo=self.with_sudo,
            stdin_pipe=stdin_pipe,
            stdout_pipe=stdout_pipe,
        )

    def capture(self, cmd):
        return run_cmd(cmd, True, with_sudo=self.with_sudo)

    def read_file(self, path):
        """Read a file from the mounted image."""
        self._ensure_mounted()
        file_path = self._get_full_path(path)
        return self.capture(["cat", file_path])

    def has_file(self, path):
        """Check if a file exists at the given path in the mounted image."""
        self._ensure_mounted()
        file_path = self._get_full_path(path)
        return self.run(["test", "-f", file_path]) == 0

    def open_file(self, path):
        """Open a file from the mounted image and return a byte stream."""
        self._ensure_mounted()
        file_path = self._get_full_path(path)
        return run_cmd(["cat", file_path], with_sudo=self.with_sudo, return_pipe=True)

    def copy_out_file(self, source_path, dest_path):
        """Copy a file from the mounted image to a destination path on disk."""
        self._ensure_mounted()

        with self.open_file(source_path) as source_stream:
            with open(dest_path, "wb") as dest_file:
                shutil.copyfileobj(source_stream, dest_file)

    def read_dir(self, path):
        """List files in a directory within the mounted image."""
        self._ensure_mounted()
        dir_path = self._get_full_path(path)
        output = self.capture(["ls", "-1", dir_path])
        return output.split("\n") if output.strip() else []

    def copy_in_file(self, source_path, dest_path):
        """Copy a file from the host filesystem into the mounted image."""
        self._ensure_mounted()

        dest_file_path = self._get_full_path(dest_path)

        with open(source_path, "rb") as source_file:
            self.run(
                ["tee", dest_file_path],
                stdin_pipe=source_file,
                stdout_pipe=subprocess.DEVNULL,
            )


def podman_image_exists(image):
    return run_cmd(["podman", "image", "exists", image]) == 0


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
        with PodmanImageMount(image) as mount:
            content = mount.read_file("/etc/build-info")
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
            res = run_cmd(cmdline)

            if res == 0:
                src = os.path.join(tmpdir, src_path)
                log.debug("Copying: %s to %s", src, dest_path)
                shutil.copyfile(src, dest_path, follow_symlinks=False)
            return res

        finally:
            # Need sudo to have permissions to clean up the tmpdir
            run_cmd(["rm", "-rf", tmpdir])
