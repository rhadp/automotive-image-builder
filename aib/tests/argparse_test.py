import pytest

from aib.main import parse_args


@pytest.mark.parametrize("arg_before_subcommand", [True, False])
@pytest.mark.parametrize(
    "subcommand,arg_name,arg_value,extra_args,expected_value",
    [
        (
            "build",
            "--container",
            [],
            ["--export", "qcow2", "test.mpp.yml", "output"],
            True,
        ),
        ("build", "--vm", [], ["--export", "qcow2", "test.mpp.yml", "output"], True),
        ("compose", "--container", [], ["test.mpp.yml", "output.json"], True),
        (
            "compose",
            "--include",
            ["/some/path"],
            ["test.mpp.yml", "output.json"],
            "/some/path",
        ),
        ("list-dist", "--include", ["/some/path"], [], "/some/path"),
    ],
)
def test_args_work_before_and_after_subcommands(
    arg_before_subcommand, subcommand, arg_name, arg_value, extra_args, expected_value
):
    """Test that --container, --vm, and --include work both before and after subcommands."""
    if arg_before_subcommand:
        args = [arg_name] + arg_value + [subcommand] + extra_args
    else:
        args = [subcommand] + [arg_name] + arg_value + extra_args

    parsed = parse_args(args, "")

    # Derive attribute name from argument name
    attr_name = arg_name.lstrip("--").replace("-", "_")
    attr_value = getattr(parsed, attr_name)

    # Check the argument was parsed correctly
    if isinstance(expected_value, bool):
        assert attr_value is expected_value
    elif isinstance(expected_value, str):
        # For list arguments like --include
        assert expected_value in attr_value
