#!/usr/bin/env python3

import os

from .utils import extract_comment_header
from .arguments import (
    command,
    LIST_ARGS,
)


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


@command(
    help="list available distributions",
    shared_args=["include"],
    args=[LIST_ARGS],
)
def list_distro(args, _tmpdir, _runner):
    """List all the available distributions available for --distro."""
    list_ipp_items(args, "distro")


@command(
    help="list available targets",
    shared_args=["include"],
    args=[LIST_ARGS],
)
def list_targets(args, _tmpdir, _runner):
    """List all the available targets available for --target."""
    list_ipp_items(args, "targets")
