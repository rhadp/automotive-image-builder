import pytest
from unittest.mock import MagicMock, patch

from aib import AIBParameters
from aib.main import parse_args
from aib.runner import Runner


BASE_DIR = "/usr/lib/automotive-image-builder"


class AnyListContaining(str):
    def __eq__(self, other):
        return self in other


class ListNotContaining(str):
    def __eq__(self, other):
        for o in other:
            if o == str(self):
                return False
        return True


def args_for(use_container, use_user_container):
    args = []
    if use_container:
        args.append("--container")
    if use_user_container:
        args.append("--user-container")
    return args


@pytest.mark.parametrize("use_sudo_for_root", [True, False])
@pytest.mark.parametrize(
    "use_container,use_user_container", [(False, False), (True, False), (False, True)]
)
@patch("aib.runner.subprocess")
def test_run_args_root(
    subprocess_mock, use_sudo_for_root, use_container, use_user_container
):
    subprocess_run = MagicMock()
    subprocess_mock.run = subprocess_run
    args = args_for(use_container, use_user_container)
    runner = Runner(
        AIBParameters(parse_args(args, base_dir=BASE_DIR), base_dir=BASE_DIR)
    )
    runner.use_sudo_for_root = use_sudo_for_root

    cmd = ["touch", "example"]
    runner.run_as_root(cmd)

    subprocess_run.assert_called_once_with(ListNotContaining("podman"), check=True)
    if use_sudo_for_root:
        subprocess_run.assert_called_once_with(AnyListContaining("sudo"), check=True)


@pytest.mark.parametrize("use_sudo_for_root", [True, False])
@pytest.mark.parametrize(
    "use_container,use_user_container", [(False, False), (True, False), (False, True)]
)
@patch("aib.runner.subprocess")
def test_run_args_container(
    subprocess_mock, use_sudo_for_root, use_container, use_user_container
):
    subprocess_run = MagicMock()
    subprocess_mock.run = subprocess_run
    args = args_for(use_container, use_user_container)
    runner = Runner(
        AIBParameters(parse_args(args, base_dir=BASE_DIR), base_dir=BASE_DIR)
    )
    runner.use_sudo_for_root = use_sudo_for_root

    cmd = ["touch", "example"]
    runner.run_in_container(cmd)

    if use_container or use_user_container:
        subprocess_run.assert_called_once_with(AnyListContaining("podman"), check=True)
    else:
        subprocess_run.assert_called_once_with(ListNotContaining("podman"), check=True)

    if use_sudo_for_root and not use_user_container:
        subprocess_run.assert_called_once_with(AnyListContaining("sudo"), check=True)
    else:
        subprocess_run.assert_called_once_with(ListNotContaining("sudo"), check=True)


@pytest.mark.parametrize("use_sudo_for_root", [True, False])
@pytest.mark.parametrize(
    "use_container,use_user_container", [(False, False), (True, False), (False, True)]
)
@patch("aib.runner.subprocess")
def test_run_args_osbuild(
    subprocess_mock, use_sudo_for_root, use_container, use_user_container
):
    subprocess_run = MagicMock()
    subprocess_mock.run = subprocess_run
    args = args_for(use_container, use_user_container)
    runner = Runner(
        AIBParameters(parse_args(args, base_dir=BASE_DIR), base_dir=BASE_DIR)
    )
    runner.use_sudo_for_root = use_sudo_for_root

    cmd = ["touch", "example"]
    runner.run_in_container(cmd, need_osbuild_privs=True)

    if use_container or use_user_container:
        subprocess_run.assert_called_once_with(AnyListContaining("podman"), check=True)
    else:
        subprocess_run.assert_called_once_with(ListNotContaining("podman"), check=True)

    if use_sudo_for_root and not use_user_container:
        subprocess_run.assert_called_once_with(AnyListContaining("sudo"), check=True)
    else:
        subprocess_run.assert_called_once_with(ListNotContaining("sudo"), check=True)


@pytest.mark.parametrize("use_sudo_for_root", [True, False])
@pytest.mark.parametrize(
    "use_container,use_user_container", [(False, False), (True, False), (False, True)]
)
@patch("aib.runner.subprocess")
def test_run_args_user(
    subprocess_mock, use_sudo_for_root, use_container, use_user_container
):
    subprocess_run = MagicMock()
    subprocess_mock.run = subprocess_run
    args = args_for(use_container, use_user_container)
    runner = Runner(
        AIBParameters(parse_args(args, base_dir=BASE_DIR), base_dir=BASE_DIR)
    )
    runner.use_sudo_for_root = use_sudo_for_root

    cmd = ["touch", "example"]
    runner.run_as_user(cmd)

    if use_container or use_user_container:
        subprocess_run.assert_called_once_with(AnyListContaining("podman"), check=True)
    else:
        subprocess_run.assert_called_once_with(ListNotContaining("podman"), check=True)

    if use_sudo_for_root and use_container:
        subprocess_run.assert_called_once_with(AnyListContaining("sudo"), check=True)
    else:
        subprocess_run.assert_called_once_with(ListNotContaining("sudo"), check=True)


@pytest.mark.parametrize(
    "container_autoupdate,use_non_root,volumes",
    [
        (False, False, []),
        (False, False, ["vol1"]),
        (False, False, ["vol1", "vol2"]),
        (True, False, []),
        (True, False, ["vol1"]),
        (True, False, ["vol1", "vol2"]),
        (False, True, []),
        (False, True, ["vol1"]),
        (False, True, ["vol1", "vol2"]),
        (True, True, []),
        (True, True, ["vol1"]),
        (True, True, ["vol1", "vol2"]),
    ],
)
def test_collect_podman_args(container_autoupdate, use_non_root, volumes):
    args = ["--container"]
    if container_autoupdate:
        args += ["--container-autoupdate"]
    runner = Runner(
        AIBParameters(parse_args(args, base_dir=BASE_DIR), base_dir=BASE_DIR)
    )
    for v in volumes:
        runner.add_volume(v)
    podman_args = runner._collect_podman_args(False, use_non_root, False)

    index = 3
    assert podman_args[:2] == ["--rm", "--workdir"]
    assert podman_args[index] == "--read-only=false"
    index = index + 1
    # Check volumes are added
    if podman_args[index : index + 2] == ["-v", f"{BASE_DIR}:{BASE_DIR}"]:  # noqa: E203
        index += 2  # Due to volume sorted by path this can appear before or after the other volumes
    for v in volumes:
        assert podman_args[index] == "-v"
        assert v in podman_args[index + 1] and ":" in podman_args[index + 1]
        index += 2
    if podman_args[index : index + 2] == ["-v", f"{BASE_DIR}:{BASE_DIR}"]:  # noqa: E203
        index += 2  # Due to volume sorted by path this can appear before or after the other volumes
    # Check container autoupdate
    if container_autoupdate:
        assert podman_args[index] == "--pull=newer"
        index += 1
    # Check use non root options
    if use_non_root:
        assert podman_args[index] == "--user"
