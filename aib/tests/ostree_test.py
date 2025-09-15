"""
aib.ostree test suite
"""

import logging
import tempfile
import os.path

from _pytest.logging import LogCaptureFixture

from aib import ostree


class MockRunner:
    """
    Mock runner for testing OSTree object
    """

    def __init__(self, with_output=True):
        self.cmdline = None
        self.capture_output = None
        self.with_output = with_output

    def run_as_user(self, cmdline, capture_output=False):
        """
        captures parameters passed and save them for inspection
        """
        self.cmdline = cmdline
        self.capture_output = capture_output
        if capture_output and self.with_output:
            return "first line\nsecond line\n"
        return ""


def test_init_without_repo(caplog: LogCaptureFixture):
    """
    Ensure repo gets initialized if not existing yet
    """
    runner = MockRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        path = os.path.join(tmpdirname, "missing_dir")
        with caplog.at_level(logging.DEBUG, logger=ostree.log.name):
            instance = ostree.OSTree(path, runner)
            assert f"Initializing repo {path}" in caplog.text
        assert "init" in instance.runner.cmdline


def test_init_with_existing_repo(caplog: LogCaptureFixture):
    """
    Ensure repo is not being initialized if it already exists
    """
    runner = MockRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        with caplog.at_level(logging.DEBUG, logger=ostree.log.name):
            instance = ostree.OSTree(tmpdirname, runner)
            # Nothing got logged
            assert caplog.text == ""
        # runner didn't execute any command
        assert instance.runner.cmdline is None


def test_refs():
    """
    Test refs method, not testing ostree itself.
    """
    runner = MockRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        instance = ostree.OSTree(tmpdirname, runner)
        out = instance.refs()
        assert out == ["first line", "second line", ""]
        assert "refs" in instance.runner.cmdline
        assert instance.runner.capture_output is True
    # if no output is returned by the runner, returns an empty list
    silent_runner = MockRunner(with_output=False)
    with tempfile.TemporaryDirectory() as tmpdirname:
        instance = ostree.OSTree(tmpdirname, silent_runner)
        out = instance.refs()
        assert out == []


def test_rev_parse():
    """
    Test rev_parse method, not testing ostree itself.
    """
    runner = MockRunner()
    with tempfile.TemporaryDirectory() as tmpdirname:
        instance = ostree.OSTree(tmpdirname, runner)
        out = instance.rev_parse("ref")
    assert out == "first line\nsecond line\n"
    assert "rev-parse" in instance.runner.cmdline
    assert instance.runner.capture_output is True
