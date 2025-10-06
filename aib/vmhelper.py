#!/usr/bin/env python3

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import shlex

from . import log

rpms = [
    "filesystem",
    "podman",
    "util-linux",
    "tar",
    "kernel-automotive-modules",
]


def print_error(s):
    print(s, file=sys.stderr)


def exit_error(s):
    print_error("Error: " + s)
    sys.exit(1)


def runcmd(cmdline, **opts):
    log.info("Running: %s", shlex.join(cmdline))
    try:
        subprocess.run(cmdline, check=True, **opts)
    except FileNotFoundError:
        print(f"Required program '{cmdline[0]}' missing, please install.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        sys.exit(1)  # cmd will have printed the error


def goarch(arch):
    if arch == "x86_64":
        return "amd64"
    if arch == "aarch64":
        return "arm64"
    return arch


def create_vm_image(base_dir, arch, dest_image, dest_kernel):
    with tempfile.TemporaryDirectory(
        prefix="automotive-image-vm-", dir="/var/tmp"
    ) as tmpdir:
        cachedir = os.path.join(tmpdir, "_dnfcache")
        rootfsdir = os.path.join(tmpdir, "rootfs")
        cmd = [
            "dnf",
            "install",
            "-q",
            "-y",
            "-c",
            os.path.join(base_dir, "files/dnf-aibvm-init.conf"),
            "--forcearch",
            arch,
            f"--setopt=cachedir={cachedir}",
            f"--installroot={rootfsdir}",
            "--releasever",
            "9",
        ] + rpms
        runcmd(cmd)

        shutil.copyfile(
            os.path.join(base_dir, "files/aibvm-init"),
            os.path.join(rootfsdir, "sbin/init"),
        )

        erofs_file = os.path.join(tmpdir, "rootfs.erofs")
        runcmd(["mkfs.erofs", erofs_file, rootfsdir], stdout=subprocess.DEVNULL)

        runcmd(
            [
                "qemu-img",
                "convert",
                "-f",
                "raw",
                "-O",
                "qcow2",
                "-c",
                erofs_file,
                dest_image,
            ]
        )

        modulesdir = os.path.join(rootfsdir, "usr/lib/modules")
        versions = os.listdir(modulesdir)
        runcmd(
            [
                "cp",
                os.path.join(modulesdir, versions[0], "vmlinuz"),
                dest_kernel,
            ]
        )


def mk_var(path):
    with tempfile.TemporaryDirectory(
        prefix="automotive-image-vm-", dir="/var/tmp"
    ) as tmpdir:
        rawfile = os.path.join(tmpdir, "var.ext4")
        with open(rawfile, "wb") as f:
            f.seek(128 * 1024 * 1024 * 1024)
            f.truncate()
        runcmd(["mkfs", "-q", "-t", "ext4", rawfile])
        runcmd(["qemu-img", "convert", "-f", "raw", "-O", "qcow2", rawfile, path])


def get_container(path, arch, container):
    runcmd(
        [
            "skopeo",
            f"--override-arch={goarch(arch)}",
            "copy",
            f"docker://{container}",
            f"docker-archive:{path}:{container}",
        ],
        stdout=subprocess.DEVNULL,
    )


def find_qemu(arch):
    binary_names = [f"qemu-system-{arch}"]
    if arch == platform.machine():
        binary_names.append("qemu-kvm")

    for binary_name in binary_names:
        if "QEMU_BUILD_DIR" in os.environ:
            p = os.path.join(os.environ["QEMU_BUILD_DIR"], binary_name)
            if os.path.isfile(p):
                return p
            else:
                exit_error(f"Can't find {binary_name}")

        qemu_bin_dirs = ["/usr/bin", "/usr/libexec"]
        if "PATH" in os.environ:
            qemu_bin_dirs += os.environ["PATH"].split(":")

        for d in qemu_bin_dirs:
            p = os.path.join(d, binary_name)
            if os.path.isfile(p):
                return p

    exit_error(f"Can't find {binary_name}")


def qemu_available_accels(qemu):
    cmd = qemu + " -accel help"
    info = subprocess.check_output(cmd.split(" ")).decode("utf-8")
    accel_list = []
    for accel in ("kvm", "xen", "hvf", "hax", "tcg"):
        if info.find(accel) > 0:
            accel_list.append(accel)
    return accel_list


def run_virtiofs_server(socket, sharedir):
    vio_args = [
        "/usr/libexec/virtiofsd",
        "--socket-path=" + socket,
        "-o",
        "source=" + sharedir,
        "-o",
        "cache=always",
        "--log-level",
        "off",
    ]
    log.info("Running: %s", shlex.join(vio_args))
    return subprocess.Popen(vio_args)


def run_vm(
    arch,
    kernel,
    rootimg,
    var_image,
    container_file,
    sharedir,
    script,
    memory,
    container_image_name,
    extra_kargs,
):
    qemu = find_qemu(arch)
    accel_list = qemu_available_accels(qemu)
    qemu_args = [qemu, "-nographic", "--kernel", kernel]

    num_cpus = os.cpu_count() or 1

    tty = "ttyS0"
    if arch == "x86_64":
        machine = "q35"
        cpu = "qemu64,+ssse3,+sse4.1,+sse4.2,+popcnt"
    elif arch == "aarch64":
        tty = "ttyAMA0"
        machine = "virt"
        cpu = "cortex-a57"
        # for up to 8 cores (limitation of qemu-system-aarch64)
        num_cpus = min(num_cpus, 8)
    else:
        exit_error(f"unsupported architecture {arch}")

    if num_cpus > 1:
        qemu_args += ["-smp", str(num_cpus)]

    if arch == platform.machine():
        if "kvm" in accel_list and os.path.exists("/dev/kvm"):
            qemu_args += ["-enable-kvm"]
        elif "hvf" in accel_list:
            qemu_args += ["-accel", "hvf"]
        cpu = "host"

    tmpdir = tempfile.TemporaryDirectory(prefix="aibvm")
    status_file = os.path.join(tmpdir.name, "exit_status")
    with open(status_file, "w", encoding="utf8") as f:
        f.write("1\n")

    # fmt: off
    qemu_args += [
        "-append", f"root=/dev/vda console={tty} loglevel=3 CONTAINER={container_image_name} " + extra_kargs,  # noqa: E501
        "-m", str(memory),
        "-machine", machine,
        "-cpu", cpu,
        "-drive", f"file={rootimg},snapshot=on,media=disk,format=qcow2,if=virtio,id=rootdisk",  # noqa: E501
        "-drive", f"file={var_image},media=disk,format=qcow2,if=virtio,id=vardisk",             # noqa: E501
        "-drive", f"file={script},media=disk,format=raw,if=virtio,id=rundisk",                  # noqa: E501
        "-drive", f"file={status_file},media=disk,format=raw,if=virtio,id=statusfile",          # noqa: E501
        "-drive", f"file={container_file},media=disk,format=raw,if=virtio,id=containerdisk"     # noqa: E501
    ]
    # fmt: on

    virtiod = None
    if sharedir:
        if not os.path.isdir(sharedir):
            exit_error(f"Shared dir {sharedir} is not a valid directory")

        vhostsocket = os.path.join(tmpdir.name, "vhost")
        virtiod = run_virtiofs_server(vhostsocket, sharedir)

        # fmt: off
        qemu_args += [
            "-chardev", "socket,id=char0,path=" + vhostsocket,
            "-device", "vhost-user-fs-pci,queue-size=1024,chardev=char0,tag=host",  # noqa: E501
            "-object", "memory-backend-file,id=mem,size="
            + str(memory) + ",mem-path=/dev/shm,share=on",
            "-numa", "node,memdev=mem"
        ]
        # fmt: on
        print(
            f"Sharing directory {sharedir}, mount using 'mount -t virtiofs host /mnt'"  # noqa: E501
        )

    runcmd(qemu_args)

    if virtiod:
        virtiod.terminate()

    res = 1
    with open(status_file, "r", encoding="utf8") as f:
        res_data = f.read()
        res = int(res_data.splitlines()[0])

    tmpdir.cleanup()

    return res
