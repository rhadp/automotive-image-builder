"""Helper functions for tests."""


def get_dummy_callbacks():
    """Get dummy callbacks for testing parse_args."""

    def dummy_callback(*args, **kwargs):
        pass

    def no_subcommand_callback(_args, _tmpdir, _runner):
        from aib import log

        log.info("No subcommand specified, see --help for usage")

    return {
        "build_bootc": dummy_callback,
        "build_traditional": dummy_callback,
        "build_bootc_builder": dummy_callback,
        "build": dummy_callback,
        "bootc_to_disk_image": dummy_callback,
        "bootc_extract_for_signing": dummy_callback,
        "bootc_inject_signed": dummy_callback,
        "bootc_reseal": dummy_callback,
        "bootc_prepare_reseal": dummy_callback,
        "list_distro": dummy_callback,
        "list_targets": dummy_callback,
        "listrpms": dummy_callback,
        "download": dummy_callback,
        "no_subcommand": no_subcommand_callback,
    }
