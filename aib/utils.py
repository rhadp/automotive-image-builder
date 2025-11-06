import base64
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_comment_header(file):
    lines = []
    for line in file:
        line = line.strip()
        if not line.startswith("#"):
            break
        lines.append(line[1:])

    # Unindent
    min_indent = -1
    for line in lines:
        indent = 0
        for c in line:
            if c == " ":
                indent = indent + 1
            else:
                if min_indent < 0:
                    min_indent = indent
                else:
                    min_indent = min(indent, min_indent)
                break

    if min_indent > 0:
        for i in range(len(lines)):
            lines[i] = lines[i][min_indent:]

    # Remove trailing empty lines
    while len(lines) > 0 and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def get_osbuild_major_version(runner, use_container):
    osbuild_version = runner.run_as_user(
        ["/usr/bin/osbuild", "--version"],
        capture_output=True,
    )
    osbuild_major_version = osbuild_version.split()[-1].split(".")[0]

    return int(osbuild_major_version)


def detect_initrd_compression(path):
    with open(path, "rb") as f:
        head = f.read(16)

    def u32_le(b):
        return int.from_bytes(b[:4], "little") if len(b) >= 4 else -1

    magic32 = u32_le(head)

    # LZ4 family
    if magic32 == 0x184D2204:  # 04 22 4D 18
        return "lz4"  # modern frame
    if magic32 == 0x184C2102:  # 02 21 4C 18
        return "lz4-legacy"
    if 0x184D2A50 <= magic32 <= 0x184D2A5F:  # P* M 18 .. P/*M18
        return "lz4-skippable"

    # Other common ones
    if head.startswith(b"\x1f\x8b"):
        return "gzip"
    if head.startswith(b"\xfd\x37\x7a\x58\x5a\x00"):
        return "xz"
    if head.startswith(b"\x28\xb5\x2f\xfd"):
        return "zstd"
    if head.startswith(b"BZh"):
        return "bzip2"

    # Raw/uncompressed newc cpio (ASCII)
    if head.startswith(b"070701") or head.startswith(b"070702"):
        return "cpio"

    # lzo/lzop (less common for initramfs, but seen)
    if head.startswith(b"\x89LZO\x00\x0d\x0a\x1a\x0a"):
        return "lzo"

    return "unknown"


def initrd_compressor_for(kind):
    if kind == "gzip":
        return ["gzip", "-c"]
    if kind == "xz":
        return ["xz", "-C", "crc32", "-z", "-c"]
    if kind == "zstd":
        return ["zstd", "-q", "-c"]
    if kind == "lz4":
        return ["lz4", "-9", "-c"]  # modern
    if kind == "lz4-legacy":
        return ["lz4", "-l", "-9", "-c"]  # legacy: note the -l
    if kind == "bzip2":
        return ["bzip2", "-c"]
    if kind == "cpio":
        return []  # no compression; append raw cpio
    if kind == "lzo":
        return ["lzop", "-c"]
    raise RuntimeError(f"Unsupported/unknown compression: {kind}")


def create_cpio_archive(dest, basedir, files, compression):
    # Start up cpio
    cpio_cmd = ["cpio", "--null", "-o", "-H", "newc", "--owner", "0:0"]
    try:
        cpio_proc = subprocess.Popen(
            cpio_cmd,
            cwd=basedir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("cpio not found in PATH")

    # Stream files to cpio, and then close stdin
    assert cpio_proc.stdin is not None
    cpio_proc.stdin.write(b"\x00".join(p.encode() for p in files) + b"\x00")
    cpio_proc.stdin.close()

    comp_cmd = initrd_compressor_for(compression)
    comp_proc = None
    if comp_cmd:
        try:
            comp_proc = subprocess.Popen(
                comp_cmd,
                stdin=cpio_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as e:
            cpio_proc.kill()
            raise RuntimeError(
                f"compressor missing for {compression}: {comp_cmd[0]}"
            ) from e

        cpio_proc.stdout.close()  # Owned by compressor now
        pipe_stdout = comp_proc.stdout
    else:
        pipe_stdout = cpio_proc.stdout

    # Write pipeline output to dest
    with open(dest, "wb") as out:
        shutil.copyfileobj(pipe_stdout, out, length=1024 * 1024)
    pipe_stdout.close()

    comp_rc = 0
    if comp_proc:
        comp_stdout, comp_stderr = comp_proc.communicate()
        comp_rc = comp_proc.returncode

    # Note: We can't user cpio_proc.communicate() here because we closed stdin
    cpio_rc = cpio_proc.wait()
    cpio_stderr = cpio_proc.stderr.read().decode(errors="ignore")

    if cpio_rc != 0:
        raise RuntimeError(f"cpio failed (rc={cpio_rc}): {cpio_stderr}")

    if comp_rc != 0:
        raise RuntimeError(f"{' '.join(comp_cmd)} failed (rc={comp_rc}): {comp_stderr}")


def openssl_stdout(*args, passargs=None):
    args = list(args)
    if passargs:
        args = args + ["-passin", passargs]
    res = subprocess.run(
        ["openssl"] + args, stdout=subprocess.PIPE, input=None, check=True
    )
    return res.stdout


def read_public_key(pemfile, passargs=None):
    # Extract the public parts from key (last 32 byte in PEM file)
    pubkey = openssl_stdout(
        "pkey", "-outform", "DER", "-pubout", "-in", pemfile, passargs=passargs
    )[-32:]

    # Ostree stores keys in base64
    pubkey_b64 = base64.b64encode(pubkey).decode("utf8")

    return pubkey_b64


def read_keys(pemfile, passargs=None):
    # Extract the seed/public parts from generated key (last 32 byte in PEM file)
    pubkey = openssl_stdout(
        "pkey", "-outform", "DER", "-pubout", "-in", pemfile, passargs=passargs
    )[-32:]
    seed = openssl_stdout("pkey", "-outform", "DER", "-in", pemfile, passargs=passargs)[
        -32:
    ]

    # Private key is seed and public key joined
    seckey = seed + pubkey

    # Ostree stores keys in base64
    pubkey_b64 = base64.b64encode(pubkey).decode("utf8")
    seckey_b64 = base64.b64encode(seckey).decode("utf8")

    return (pubkey_b64, seckey_b64)


# Generates an (unencrypted) PEM format ed25519 private key at path
def generate_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        keypath = os.path.join(tmpdir, "key")
        cmd = [
            "openssl",
            "genpkey",
            "-algorithm",
            "ed25519",
            "-outform",
            "PEM",
            "-out",
            keypath,
        ]
        subprocess.run(cmd, encoding="utf8", stdout=sys.stderr, input=None, check=True)
        return read_keys(keypath)


# This is compatible with tempdir.TemporaryDirectory, but falls back to sudo rm -rf on permission errors
class SudoTemporaryDirectory:
    def __init__(self, suffix=None, prefix=None, dir=None, use_sudo_fallback=True):
        self._path = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir))
        self.name = str(self._path)
        self._keep_once = False
        self._use_sudo = use_sudo_fallback
        # Remember the base directory for safety checks
        self._base = (
            Path(dir).resolve() if dir else Path(tempfile.gettempdir()).resolve()
        )
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._keep_once:
            self._keep_once = False
            return
        self.cleanup()

    def detach(self):
        """Skip cleanup at the end of the *current* with-block only."""
        self._keep_once = True
        return self

    # Some safety checks:
    def _is_safe_to_delete(self, path):
        try:
            rp = path.resolve()
        except FileNotFoundError:
            return True

        if rp == Path("/") or str(rp) == "":
            return False

        if not rp.is_dir():
            return False

        try:
            rp.relative_to(self._base)
        except ValueError:
            # Not under base dir
            return False

        # Require minimum length to avoid deleting very short critical paths
        return len(str(rp)) > len(str(self._base)) + 3

    def cleanup(self):
        if self._closed:
            return
        self._closed = True

        p = self._path
        if not p.exists():
            return

        # Try normal deletion first
        try:
            shutil.rmtree(p)
            return
        except Exception as e:
            last_err = e

        # Optionally try sudo fallback
        if self._use_sudo and self._is_safe_to_delete(p):
            try:
                subprocess.run(
                    ["sudo", "rm", "-rf", "--", str(p)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except subprocess.CalledProcessError as e:
                last_err = e

        # If we reach here, cleanup failed
        raise RuntimeError(f"Failed to cleanup temp directory {p!s}") from last_err

    def __str__(self):
        return self.name

    def __fspath__(self):
        return self.name

    def path(self):
        return self._path
