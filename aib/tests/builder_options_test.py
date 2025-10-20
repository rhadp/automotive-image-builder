import pytest
import re

from aib.main import parse_args
from aib import AIBParameters


BASEDIR = "/tmp/automotive-image-builder"


@pytest.mark.parametrize(
    "subcmd",
    [
        "list-dist",
        "list-targets",
        "compose",
        "build",
    ],
)
def test_valid_subcommands(subcmd):
    with pytest.raises(SystemExit) as e:
        parse_args([subcmd, "--help"], base_dir="")
    assert e.value.code == 0


def test_invalid_subcommand():
    with pytest.raises(SystemExit) as e:
        parse_args(["invalid", "--help"], base_dir="")
    assert e.value.code == 2


def test_no_subcommand(caplog):
    args = parse_args([], base_dir="")
    args.func(_args=args, _tmpdir="", _runner=None)
    assert "No subcommand specified, see --help for usage" in caplog.text


def test_build_required_positional(capsys):
    with pytest.raises(SystemExit) as e:
        parse_args(["build"], base_dir="")
    assert e.value.code == 2
    assert (
        "error: the following arguments are required: --export, manifest, out"
        in capsys.readouterr().err
    )


@pytest.mark.parametrize(
    "mpp_args,expected",
    [
        (
            ["--mpp-arg=--cache", "--mpp-arg", "/path/to/cache"],
            ["--cache", "/path/to/cache"],
        ),
        (
            ["--mpp-arg=--cache", "--mpp-arg=/path/to/cache"],
            ["--cache", "/path/to/cache"],
        ),
    ],
)
def test_build_mpp_arg(mpp_args, expected):
    args = parse_args(
        ["build"] + mpp_args + ["--export", "qcow2"] + ["manifest", "out"],
        base_dir="",
    )
    assert args.mpp_arg == expected


def test_build_cache_arg():
    cache_path = "/path/to/cache"
    args = parse_args(
        [
            "build",
            "--cache",
            cache_path,
            "--export",
            "qcow2",
            "manifest",
            "out",
        ],
        base_dir="",
    )
    assert args.cache == cache_path


@pytest.mark.parametrize(
    "includes",
    [
        [],
        ["dir1"],
        ["dir1", "dir2"],
    ],
)
def test_aib_paramters(includes):
    base_dir = "base_dir"
    argv = []
    for inc in includes:
        argv.extend(["--include", inc])
    args = AIBParameters(args=parse_args(argv, base_dir), base_dir=base_dir)
    assert args.base_dir == base_dir
    assert args.include_dirs == [base_dir] + includes


@pytest.mark.parametrize(
    "logfile,build_dir,progress,expected_contains",
    [
        # Custom logfile path
        ("/custom/path/build.log", "/build", True, "/custom/path/build.log"),
        # Default logfile with build_dir
        (None, "/build", True, "/build/automotive-image-builder-"),
        # No logfile when progress is disabled and no logfile specified
        (None, "/build", False, None),
        # Logfile specified but progress disabled (should still return logfile)
        ("/custom/log.log", "/build", False, "/custom/log.log"),
    ],
)
def test_aib_parameters_log_file_property(
    logfile, build_dir, progress, expected_contains
):
    """Test AIBParameters.log_file property returns correct path."""
    argv = ["build", "--export", "qcow2", "manifest", "out"]

    if logfile:
        argv.extend(["--logfile", logfile])

    if build_dir:
        argv.extend(["--build-dir", build_dir])

    if progress:
        argv.append("--progress")

    args = parse_args(argv, base_dir="")
    params = AIBParameters(args=args, base_dir="")

    if expected_contains is None:
        assert params.log_file is None
    else:
        assert params.log_file is not None
        assert expected_contains in params.log_file

        # If it's a generated path, verify it has the timestamp format
        if "automotive-image-builder-" in expected_contains and logfile is None:
            # Should match pattern: automotive-image-builder-YYYYMMDD-HHMMSS.log
            pattern = r"automotive-image-builder-\d{8}-\d{6}\.log"
            assert re.search(
                pattern, params.log_file
            ), f"Log file path {params.log_file} doesn't match expected format"


def test_aib_parameters_log_file_property_no_build_dir():
    """Test AIBParameters.log_file property when build_dir is not set but progress is enabled."""
    argv = ["build", "--export", "qcow2", "--progress", "manifest", "out"]

    args = parse_args(argv, base_dir="")
    params = AIBParameters(args=args, base_dir="")

    # Should return None when build_dir is not set (caught TypeError internally)
    assert params.log_file is None
