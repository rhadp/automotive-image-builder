#!/usr/bin/env python3
"""
write_simg.py - Write Android sparse image to block device
"""

import argparse
import fcntl
import os
import stat
import struct
import sys

SPARSE_HEADER_MAGIC = 0xED26FF3A
CHUNK_TYPE_RAW = 0xCAC1
CHUNK_TYPE_FILL = 0xCAC2
CHUNK_TYPE_DONT_CARE = 0xCAC3

use_verbose = False


def verbose(str):
    if use_verbose:
        print(str)


def is_block_device(path):
    try:
        st = os.stat(path)
        return stat.S_ISBLK(st.st_mode)
    except OSError:
        return False


def get_block_device_size(path):
    with open(path, "rb") as f:
        fd = f.fileno()
        BLKGETSIZE64 = 0x80081272
        size_bytes = fcntl.ioctl(fd, BLKGETSIZE64, b"\x00" * 8)
        return struct.unpack("Q", size_bytes)[0]


def get_block_device_info(path):
    info = {}

    # Get size
    info["size"] = get_block_device_size(path)
    info["size_gb"] = info["size"] / (1024**3)

    # Get device name (e.g., sda from /dev/sda or sda1 from /dev/sda1)
    info["name"] = os.path.basename(path)

    # Check if this is a partition
    sysfs_base = f"/sys/class/block/{info['name']}"
    is_partition = os.path.exists(f"{sysfs_base}/partition")

    info["partition"] = None
    info["parent_device"] = None

    if is_partition:
        # Read partition number
        try:
            with open(f"{sysfs_base}/partition", "r") as f:
                info["partition"] = f.read().strip()
        except Exception:
            pass

        # Get parent device name
        try:
            # The parent is a symlink like ../../sda
            parent_link = os.path.realpath(f"{sysfs_base}/..")
            info["parent_device"] = os.path.basename(parent_link)
        except Exception:
            pass

        # For partitions, device info is at ../device
        device_path = f"{sysfs_base}/../device"
    else:
        # For base devices, device info is at device
        device_path = f"{sysfs_base}/device"

    for f in ["model", "vendor", "name"]:
        id = "device_" + f
        info[id] = None
        try:
            if os.path.exists(f"{device_path}/{f}"):
                with open(f"{device_path}/{f}", "r") as f:
                    data = f.read().strip()
                    if data:
                        info[id] = data
        except Exception:
            pass

    return info


def parse_simg_header(src):
    header_data = src.read(28)
    if len(header_data) < 28:
        raise ValueError("Invalid sparse image: header too short")

    header = struct.unpack("<IHHHHIIII", header_data)
    (
        magic,
        major,
        minor,
        file_hdr_sz,
        chunk_hdr_sz,
        block_size,
        total_blocks,
        total_chunks,
        checksum,
    ) = header

    if magic != SPARSE_HEADER_MAGIC:
        raise ValueError(f"Invalid sparse image magic: 0x{magic:08x}")

    if major != 1:
        raise ValueError(f"Unsupported sparse image version: {major}.{minor}")

    if file_hdr_sz != 28:
        raise ValueError(f"Unexpected header size: {file_hdr_sz}")

    if chunk_hdr_sz != 12:
        raise ValueError(f"Unexpected chunk header size: {chunk_hdr_sz}")

    image_size = total_blocks * block_size

    return {
        "block_size": block_size,
        "total_blocks": total_blocks,
        "total_chunks": total_chunks,
        "image_size": image_size,
    }


def write_raw_chunk(src, dst, chunk_idx, chunk_sz, total_sz, offset, block_size):
    data_bytes = chunk_sz * block_size
    if total_sz != 12 + data_bytes:
        raise ValueError(
            f"Chunk {chunk_idx}: RAW total_sz mismatch: {total_sz} != {12 + data_bytes}"
        )

    dst.seek(offset)

    remaining = data_bytes
    while remaining > 0:
        to_read = min(1024 * 1024, remaining)
        data = src.read(to_read)
        if len(data) != to_read:
            raise ValueError(f"Chunk {chunk_idx}: unexpected end of data")
        dst.write(data)
        remaining -= to_read

    verbose(f"Chunk {chunk_idx}: RAW {chunk_sz} blocks at offset {offset}")
    return data_bytes


def write_fill_chunk(src, dst, chunk_idx, chunk_sz, total_sz, offset, block_size):
    if total_sz != 16:
        raise ValueError(
            f"Chunk {chunk_idx}: FILL total_sz should be 16, got {total_sz}"
        )

    fill_data = src.read(4)
    if len(fill_data) != 4:
        raise ValueError(f"Chunk {chunk_idx}: missing fill value")

    fill_value = struct.unpack("<I", fill_data)[0]

    dst.seek(offset)

    fill_block = struct.pack("<I", fill_value) * (block_size // 4)
    for _ in range(chunk_sz):
        dst.write(fill_block)

    verbose(
        f"Chunk {chunk_idx}: FILL {chunk_sz} blocks with 0x{fill_value:08x} at offset {offset}"
    )
    return chunk_sz * block_size


def write_dont_care_chunk(
    dst, chunk_idx, chunk_sz, total_sz, offset, block_size, zero_initialize
):
    if total_sz != 12:
        raise ValueError(
            f"Chunk {chunk_idx}: DONT_CARE total_sz should be 12, got {total_sz}"
        )

    if zero_initialize:
        dst.seek(offset)
        fill_block = struct.pack("<I", 0) * (block_size // 4)
        for _ in range(chunk_sz):
            dst.write(fill_block)
        verbose(
            f"Chunk {chunk_idx}: DONT_CARE {chunk_sz} blocks at offset {offset} (zeroed)"
        )
    else:
        verbose(
            f"Chunk {chunk_idx}: DONT_CARE {chunk_sz} blocks at offset {offset} (skipped)"
        )

    return chunk_sz * block_size if zero_initialize else 0


def write_simg(simg_path, output_path, is_block, zero_initialize):
    if is_block:
        if not is_block_device(output_path):
            raise ValueError(f"{output_path} is not a block device")
        device_size = get_block_device_size(output_path)

    open_mode = "r+b" if is_block else "wb"

    with open(simg_path, "rb") as src, open(output_path, open_mode) as dst:
        # Read and validate header
        hdr = parse_simg_header(src)
        block_size = hdr["block_size"]
        total_blocks = hdr["total_blocks"]
        total_chunks = hdr["total_chunks"]
        image_size = hdr["image_size"]

        if is_block:
            if device_size < image_size:
                raise ValueError(
                    f"Device too small: {device_size} bytes, need {image_size} bytes"
                )

        print(f"Sparse image: {total_blocks} blocks of {block_size} bytes")
        print(f"Total size: {image_size} bytes ({image_size // (1024**3)} GB)")
        print(f"Total chunks: {total_chunks}")
        if is_block:
            print(f"Device size: {device_size} bytes ({device_size // (1024**3)} GB)")

        written_size = 0
        current_block = 0
        for chunk_idx in range(total_chunks):
            chunk_header = src.read(12)
            if len(chunk_header) < 12:
                raise ValueError(f"Chunk {chunk_idx}: header too short")

            chunk_type, reserved, chunk_sz, total_sz = struct.unpack(
                "<HHII", chunk_header
            )

            offset = current_block * block_size

            if chunk_type == CHUNK_TYPE_RAW:
                written_size += write_raw_chunk(
                    src, dst, chunk_idx, chunk_sz, total_sz, offset, block_size
                )

            elif chunk_type == CHUNK_TYPE_FILL:
                written_size += write_fill_chunk(
                    src, dst, chunk_idx, chunk_sz, total_sz, offset, block_size
                )

            elif chunk_type == CHUNK_TYPE_DONT_CARE:
                written_size += write_dont_care_chunk(
                    dst,
                    chunk_idx,
                    chunk_sz,
                    total_sz,
                    offset,
                    block_size,
                    zero_initialize,
                )

            else:
                raise ValueError(
                    f"Chunk {chunk_idx}: unknown chunk type 0x{chunk_type:04x}"
                )

            current_block += chunk_sz

        if current_block != total_blocks:
            raise ValueError(
                f"Block count mismatch: processed {current_block}, expected {total_blocks}"
            )

        if not is_block:
            os.ftruncate(dst.fileno(), image_size)

        dst.flush()
        os.fsync(dst.fileno())

    print(
        f"\nSuccessfully wrote {written_size:,} (of {image_size:,}) bytes to {output_path}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Write Android sparse image to block device or file"
    )
    parser.add_argument("simg", help="Input sparse image file (.simg)")
    parser.add_argument("output", help="Output block device or file")
    parser.add_argument(
        "--file", action="store_true", help="Allow writing to non-block-device"
    )
    parser.add_argument("--verbose", action="store_true", help="Be more verbose")
    parser.add_argument(
        "--zero", action="store_true", help="Zero initialize don't care regions"
    )
    parser.add_argument(
        "--force", action="store_true", help="Skip safety confirmation prompt"
    )

    args = parser.parse_args()
    if args.verbose:
        global use_verbose
        use_verbose = True

    if not os.path.exists(args.simg):
        print(f"Error: {args.simg} not found", file=sys.stderr)
        sys.exit(1)

    is_block = False
    if os.path.exists(args.output):
        is_block = is_block_device(args.output)
        if not is_block and not args.file:
            print(f"Error: {args.output} is not a block device", file=sys.stderr)
            sys.exit(1)

        if not args.force:
            if is_block:
                # Get device information for warning
                dev_info = get_block_device_info(args.output)

                print("=" * 70)
                print(f"WARNING: This will write to block device {args.output}")
                print(f"Device: {dev_info['name']}")
                if dev_info["partition"]:
                    print(f"Partition: {dev_info['partition']}")
                    if dev_info["parent_device"]:
                        print(f"Parent device: {dev_info['parent_device']}")
                print(f"Size: {dev_info['size_gb']:.2f} GB ({dev_info['size']} bytes)")
                if dev_info["device_vendor"]:
                    print(f"Device Vendor: {dev_info['device_vendor']}")
                if dev_info["device_model"]:
                    print(f"Device Model: {dev_info['device_model']}")
                if dev_info["device_name"]:
                    print(f"Device Name: {dev_info['device_name']}")
                print()
                print("ALL DATA ON THIS DEVICE WILL BE PERMANENTLY LOST!")
                print("=" * 70)
            else:
                print(f"WARNING: {args.output} already exists and will be overwritten")
            response = input("Type 'yes' to continue: ")
            if response != "yes":
                print("Aborted.")
                sys.exit(0)
    else:
        if not args.file:
            print(f"Error: {args.output} not found", file=sys.stderr)
            sys.exit(1)

    try:
        write_simg(args.simg, args.output, is_block=is_block, zero_initialize=args.zero)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
