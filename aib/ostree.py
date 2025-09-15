import os

from . import log


class OSTree:
    def __init__(self, path, runner):
        self.path = path
        self.runner = runner
        if not os.path.isdir(path):
            self.repo_init()

    def repo_init(self):
        log.debug("Initializing repo %s", self.path)
        cmdline = ["ostree", "init", "--repo", self.path, "--mode", "archive"]
        self.runner.run_as_user(cmdline)

    def refs(self):
        cmdline = ["ostree", "refs", "--repo", self.path]
        out = self.runner.run_as_user(cmdline, capture_output=True)
        if out:
            return out.split("\n")
        return []

    def rev_parse(self, ref):
        cmdline = ["ostree", "rev-parse", "--repo", self.path, ref]
        out = self.runner.run_as_user(cmdline, capture_output=True)
        return out
