import pytest
import unittest
import tempfile
import os
import yaml
import jsonschema
from unittest.mock import Mock, patch

from aib import exceptions
from aib.simple import (
    without,
    parse_size,
    json_bool,
    ExtraInclude,
    Contents,
    QMContents,
    ManifestLoader,
    validateNoFusa,
    extend_with_default,
)


@pytest.mark.parametrize(
    "orig,key,res",
    [
        ({"a": 17, "b": 42}, "b", {"a": 17}),
        ({"a": 17, "b": 42}, "a", {"b": 42}),
    ],
)
def test_without(orig, key, res):
    assert without(orig, key) == res


@pytest.mark.parametrize(
    "s,res",
    [
        ("2kB", 1000 * 2),
        ("2KiB", 1024 * 2),
        ("2MB", 1000 * 1000 * 2),
        ("2MiB", 1024 * 1024 * 2),
        ("2GB", 1000 * 1000 * 1000 * 2),
        ("2GiB", 1024 * 1024 * 1024 * 2),
        ("2TB", 1000 * 1000 * 1000 * 1000 * 2),
        ("2TiB", 1024 * 1024 * 1024 * 1024 * 2),
        ("42", 42),  # Test plain number
    ],
)
def test_parse_string(s, res):
    assert parse_size(s) == res


def test_parse_unsupported_string():
    """
    Cover negative case for parse_string
    """
    with pytest.raises(TypeError):
        parse_size("2Kg")


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, "true"),
        (False, "false"),
        (1, "true"),
        (0, "false"),
        ("hello", "true"),
        ("", "false"),
        ([], "false"),
        ([1], "true"),
        (None, "false"),
    ],
)
def test_json_bool(value, expected):
    """Test json_bool function with various inputs"""
    assert json_bool(value) == expected


class TestExtraInclude(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.extra_include = ExtraInclude(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init(self):
        """Test ExtraInclude initialization"""
        self.assertEqual(self.extra_include.basedir, os.path.abspath(self.tmpdir))
        self.assertEqual(self.extra_include.content_id, 1)
        self.assertEqual(self.extra_include.file_content_inputs, {})
        self.assertEqual(self.extra_include.file_content_paths, [])

    def test_gen_id(self):
        """Test ID generation"""
        id1 = self.extra_include.gen_id()
        id2 = self.extra_include.gen_id()
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)
        self.assertEqual(self.extra_include.content_id, 3)

    def test_gen_file_input_text(self):
        """Test gen_file_input with text data"""
        data = {"text": "Hello World"}
        result = self.extra_include.gen_file_input(1, data)
        expected = {
            "type": "org.osbuild.files",
            "origin": "org.osbuild.source",
            "mpp-embed": {"id": "image_content_id_1", "text": "Hello World"},
        }
        self.assertEqual(result, expected)

    def test_gen_file_input_url(self):
        """Test gen_file_input with URL data"""
        data = {"url": "https://example.com/file.txt"}
        result = self.extra_include.gen_file_input(2, data)
        expected = {
            "type": "org.osbuild.files",
            "origin": "org.osbuild.source",
            "mpp-embed": {
                "id": "image_content_id_2",
                "url": "https://example.com/file.txt",
            },
        }
        self.assertEqual(result, expected)

    def test_gen_file_input_source_path_relative(self):
        """Test gen_file_input with relative source path"""
        data = {"source_path": "subdir/file.txt"}
        result = self.extra_include.gen_file_input(3, data)
        expected_path = os.path.normpath(os.path.join(self.tmpdir, "subdir/file.txt"))
        expected = {
            "type": "org.osbuild.files",
            "origin": "org.osbuild.source",
            "mpp-embed": {"id": "image_content_id_3", "path": expected_path},
        }
        self.assertEqual(result, expected)

    def test_gen_file_input_source_path_absolute(self):
        """Test gen_file_input with absolute source path"""
        abs_path = "/tmp/absolute/file.txt"
        data = {"source_path": abs_path}
        result = self.extra_include.gen_file_input(4, data)
        expected = {
            "type": "org.osbuild.files",
            "origin": "org.osbuild.source",
            "mpp-embed": {"id": "image_content_id_4", "path": abs_path},
        }
        self.assertEqual(result, expected)

    def test_gen_file_copy(self):
        """Test gen_file_copy"""
        result = self.extra_include.gen_file_copy(5)
        expected = {
            "from": {
                "mpp-format-string": "input://inlinefile5/{embedded['image_content_id_5']}"
            },
            "to": "tree:///image_content_5",
        }
        self.assertEqual(result, expected)

    def test_gen_file_copy_out(self):
        """Test gen_file_copy_out"""
        data = {"path": "/etc/config.txt"}
        result = self.extra_include.gen_file_copy_out(6, data)
        expected = {
            "from": "input://extra/image_content_6",
            "to": "tree:///etc/config.txt",
        }
        self.assertEqual(result, expected)

    def test_add_file_copy(self):
        """Test add_file_copy"""
        mock_contents = Mock()
        mock_contents.file_content_copy = []

        data = {"text": "content", "path": "/etc/test.txt"}
        self.extra_include.add_file_copy(mock_contents, data)

        # Check that file_content_inputs was populated
        self.assertIn("inlinefile1", self.extra_include.file_content_inputs)
        # Check that file_content_paths was populated
        self.assertEqual(len(self.extra_include.file_content_paths), 1)
        # Check that contents.file_content_copy was populated
        self.assertEqual(len(mock_contents.file_content_copy), 1)

    def test_generate_empty(self):
        """Test generate with no file content"""
        result = self.extra_include.generate()
        expected = {"version": "2", "pipelines": []}
        self.assertEqual(result, expected)

    def test_generate_with_content(self):
        """Test generate with file content"""
        mock_contents = Mock()
        mock_contents.file_content_copy = []

        data = {"text": "content", "path": "/etc/test.txt"}
        self.extra_include.add_file_copy(mock_contents, data)

        result = self.extra_include.generate()

        self.assertEqual(result["version"], "2")
        self.assertEqual(len(result["pipelines"]), 1)
        pipeline = result["pipelines"][0]
        self.assertEqual(pipeline["name"], "extra-image-content")
        self.assertEqual(len(pipeline["stages"]), 1)
        stage = pipeline["stages"][0]
        self.assertEqual(stage["type"], "org.osbuild.copy")
        self.assertIn("inputs", stage)
        self.assertIn("options", stage)


class TestContents(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mock_loader = Mock()
        self.mock_loader.defines = {"arch": "x86_64"}
        self.mock_loader.set = Mock()
        self.extra_include = ExtraInclude(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init(self):
        """Test Contents initialization"""
        data = {
            "enable_repos": ["debug"],
            "repos": [{"baseurl": "http://example.com"}],
            "rpms": ["vim", "git"],
            "container_images": ["registry.com/app:latest"],
            "add_files": [],
            "chown_files": [],
            "chmod_files": [],
            "remove_files": [],
            "make_dirs": [],
            "systemd": {"enabled": ["sshd"]},
        }

        contents = Contents(self.mock_loader, data, self.extra_include)

        self.assertEqual(contents.enable_repos, ["debug"])
        self.assertEqual(contents.repos, [{"baseurl": "http://example.com"}])
        self.assertEqual(contents.rpms, ["vim", "git"])
        self.assertEqual(contents.containers, ["registry.com/app:latest"])
        self.assertEqual(contents.systemd, {"enabled": ["sshd"]})

    def test_get_key(self):
        """Test get_key method"""
        contents = Contents(self.mock_loader, {}, self.extra_include)
        self.assertEqual(contents.get_key("test_key"), "test_key")

    def test_set_define(self):
        """Test set_define method"""
        contents = Contents(self.mock_loader, {}, self.extra_include)
        contents.set_define("test_key", "test_value")
        self.mock_loader.set.assert_called_once_with("test_key", "test_value")

    def test_set_defines_with_containers(self):
        """Test set_defines with containers"""
        data = {"container_images": ["registry.com/app:latest"], "rpms": ["vim"]}
        contents = Contents(self.mock_loader, data, self.extra_include)
        contents.set_defines()

        # Check that podman was added to rpms
        expected_rpms = ["vim", "podman"]
        self.mock_loader.set.assert_any_call("simple_rpms", expected_rpms)
        self.mock_loader.set.assert_any_call("use_containers_extra_store", True)

    def test_set_defines_with_debug_repos(self):
        """Test set_defines with debug repos"""
        data = {"enable_repos": ["debug"]}
        contents = Contents(self.mock_loader, data, self.extra_include)
        contents.set_defines()

        self.mock_loader.set.assert_any_call("simple_add_debug_repos", True)

    def test_set_defines_with_devel_repos(self):
        """Test set_defines with devel repos"""
        data = {"enable_repos": ["devel"]}
        contents = Contents(self.mock_loader, data, self.extra_include)
        contents.set_defines()

        self.mock_loader.set.assert_any_call("simple_add_devel_repos", True)

    def test_set_defines_with_arch_substitution(self):
        """Test set_defines with arch substitution in repo URLs"""
        data = {"repos": [{"baseurl": "http://example.com/$arch/repo"}]}
        contents = Contents(self.mock_loader, data, self.extra_include)
        contents.set_defines()

        expected_repos = [{"baseurl": "http://example.com/x86_64/repo"}]
        self.mock_loader.set.assert_any_call("simple_repos", expected_repos)

    def test_set_defines_with_files(self):
        """Test set_defines with file operations"""
        data = {
            "make_dirs": ["/tmp/test"],
            "chmod_files": [{"path": "/tmp/test", "mode": "755"}],
            "chown_files": [{"path": "/tmp/test", "owner": "root", "group": "root"}],
            "remove_files": [{"path": "/tmp/old"}],
        }
        contents = Contents(self.mock_loader, data, self.extra_include)
        contents.set_defines()

        self.mock_loader.set.assert_any_call("simple_mkdir", ["/tmp/test"])
        self.mock_loader.set.assert_any_call(
            "simple_chmod", {"/tmp/test": {"mode": "755"}}
        )
        self.mock_loader.set.assert_any_call(
            "simple_chown", {"/tmp/test": {"owner": "root", "group": "root"}}
        )
        self.mock_loader.set.assert_any_call("simple_remove", ["/tmp/old"])


class TestQMContents(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mock_loader = Mock()
        self.mock_loader.defines = {"arch": "x86_64"}
        self.mock_loader.set = Mock()
        self.extra_include = ExtraInclude(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_key_with_use_prefix(self):
        """Test QMContents get_key with use_ prefix"""
        qm_contents = QMContents(self.mock_loader, {}, self.extra_include)
        self.assertEqual(qm_contents.get_key("use_something"), "use_qm_something")

    def test_get_key_without_use_prefix(self):
        """Test QMContents get_key without use_ prefix"""
        qm_contents = QMContents(self.mock_loader, {}, self.extra_include)
        self.assertEqual(qm_contents.get_key("simple_rpms"), "qm_simple_rpms")


class TestValidateNoFusa(unittest.TestCase):
    def setUp(self):
        self.validator = Mock()
        self.validator.is_type = Mock()

    def test_validate_no_fusa_object_disallowed_property(self):
        """Test validateNoFusa for objects with disallowed properties"""
        self.validator.is_type.side_effect = (
            lambda instance, type_name: type_name == "object"
        )

        instance = {"allowed_prop": "value", "disallowed_prop": "value"}
        no_fusa = ["disallowed_prop"]

        errors = list(validateNoFusa(self.validator, no_fusa, instance, {}))

        self.assertEqual(len(errors), 1)
        self.assertIn("disallowed_prop", str(errors[0]))

    def test_validate_no_fusa_object_allowed_property(self):
        """Test validateNoFusa for objects with allowed properties"""
        self.validator.is_type.side_effect = (
            lambda instance, type_name: type_name == "object"
        )

        instance = {"allowed_prop": "value"}
        no_fusa = ["disallowed_prop"]

        errors = list(validateNoFusa(self.validator, no_fusa, instance, {}))

        self.assertEqual(len(errors), 0)

    def test_validate_no_fusa_string_disallowed_value(self):
        """Test validateNoFusa for strings with disallowed values"""
        self.validator.is_type.side_effect = (
            lambda instance, type_name: type_name == "string"
        )

        instance = "disallowed_value"
        no_fusa = ["disallowed_value"]

        errors = list(validateNoFusa(self.validator, no_fusa, instance, {}))

        self.assertEqual(len(errors), 1)
        self.assertIn("disallowed_value", str(errors[0]))

    def test_validate_no_fusa_number_disallowed_value(self):
        """Test validateNoFusa for numbers with disallowed values"""
        self.validator.is_type.side_effect = (
            lambda instance, type_name: type_name == "number"
        )

        instance = 42
        no_fusa = [42]

        errors = list(validateNoFusa(self.validator, no_fusa, instance, {}))

        self.assertEqual(len(errors), 1)
        self.assertIn("42", str(errors[0]))


class TestExtendWithDefault(unittest.TestCase):
    def test_extend_with_default(self):
        """Test extend_with_default function"""
        base_validator = jsonschema.Draft7Validator
        extended_validator = extend_with_default(base_validator)

        # Test that the extended validator has properties validator
        self.assertIn("properties", extended_validator.VALIDATORS)

        # Test with a schema that has defaults
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "default_name"},
                "age": {"type": "number"},
            },
        }

        instance = {"age": 30}
        validator = extended_validator(schema)

        # Validate and check if default was set
        errors = list(validator.iter_errors(instance))
        self.assertEqual(len(errors), 0)
        self.assertEqual(instance["name"], "default_name")


class TestManifestLoader(unittest.TestCase):
    def load_manifest(self, manifest, use_fusa=False):
        defines = {
            "_basedir": "/usr/lib/automotive-image-builder",
            "_workdir": "/tmp",
            "arch": "x86_64",
            "use_fusa": use_fusa,
        }

        with patch("builtins.open", mock_open_manifest_schema()):
            loader = ManifestLoader(defines)
            with patch.object(loader, "validator") as mock_validator:
                mock_validator.iter_errors.return_value = []
                with patch("yaml.dump"):
                    loader._load(manifest, "test.yml", "/tmp")
        return loader

    def test_basic(self):
        manifest = {"name": "test", "version": "1.0"}
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["name"], "test")
        self.assertEqual(loader.defines["version"], "1.0")

    def test_fusa(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "content": {
                "rpms": ["vim", "git", "podman"],
                "container_images": ["registry.redhat.io/ubi8/ubi:latest"],
                "systemd": {"enabled": ["sshd"]},
            },
        }
        loader = self.load_manifest(manifest, use_fusa=True)
        self.assertEqual(loader.defines["name"], "test")
        self.assertEqual(loader.defines["version"], "1.0")

    def test_with_qm_section(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "qm": {
                "memory_limit": {"max": "1G", "high": "800M"},
                "cpu_weight": 100,
                "container_checksum": "sha256:abcd1234",
                "content": {"rpms": ["qm-package"]},
            },
        }
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["use_qm"], True)
        self.assertEqual(loader.defines["qm_memory_max"], "1G")
        self.assertEqual(loader.defines["qm_memory_high"], "800M")
        self.assertEqual(loader.defines["qm_cpu_weight"], 100)
        self.assertEqual(loader.defines["boot_check_qm_digest"], "sha256:abcd1234")

    def test_with_network_section(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "network": {
                "static": {
                    "ip": "192.168.1.100",
                    "ip_prefixlen": 24,
                    "gateway": "192.168.1.1",
                    "dns": ["8.8.8.8"],
                    "iface": "eth0",
                    "load_module": "e1000",
                }
            },
        }
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["use_static_ip"], True)
        self.assertEqual(loader.defines["static_ip"], "192.168.1.100")
        self.assertEqual(loader.defines["static_ip_prefixlen"], "24")
        self.assertEqual(loader.defines["static_gw"], "192.168.1.1")
        self.assertEqual(loader.defines["static_dns"], ["8.8.8.8"])
        self.assertEqual(loader.defines["static_ip_iface"], "eth0")
        self.assertEqual(loader.defines["static_ip_modules"], ["e1000"])

    def test_with_auth_section(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "auth": {
                "root_password": "secret",
                "root_ssh_keys": ["ssh-rsa AAAAB3..."],
                "sshd_config": {"PermitRootLogin": "yes"},
                "groups": [{"name": "wheel"}],
                "users": [{"name": "testuser", "groups": ["wheel"]}],
            },
        }
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["root_password"], "secret")
        self.assertEqual(loader.defines["root_ssh_keys"], ["ssh-rsa AAAAB3..."])
        self.assertEqual(
            loader.defines["simple_sshd_config"], {"PermitRootLogin": "yes"}
        )
        self.assertEqual(loader.defines["simple_groups"], [{"name": "wheel"}])
        self.assertEqual(
            loader.defines["simple_users"], [{"name": "testuser", "groups": ["wheel"]}]
        )

    def test_with_kernel_section(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "kernel": {
                "kernel_package": "kernel-rt",
                "kernel_version": "5.14.0",
                "loglevel": 3,
                "debug_logging": True,
                "cmdline": ["quiet", "splash"],
                "remove_modules": ["pcspkr", "snd_pcsp"],
            },
        }
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["kernel_package"], "kernel-rt")
        self.assertEqual(loader.defines["kernel_version"], "5.14.0")
        self.assertEqual(loader.defines["kernel_loglevel"], 3)
        self.assertEqual(loader.defines["use_debug"], True)
        self.assertEqual(loader.defines["simple_kernel_opts"], ["quiet", "splash"])
        self.assertEqual(loader.defines["denylist_modules"], ["pcspkr", "snd_pcsp"])

    def test_with_image_section(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "image": {
                "image_size": "10GB",
                "hostname": "testhost",
                "ostree_ref": "rhel/9/x86_64/edge",
                "selinux_mode": "enforcing",
                "selinux_policy": "targeted",
                "selinux_booleans": {"httpd_can_network_connect": True},
                "partitions": {
                    "var": {
                        "size": "1GB",
                        "uuid": "12345678-1234-1234-1234-123456789012",
                    },
                    "home": {"size": "2GB"},
                },
            },
        }
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["image_size"], str(10 * 1000 * 1000 * 1000))
        self.assertEqual(loader.defines["hostname"], "testhost")
        self.assertEqual(loader.defines["ostree_ref"], "rhel/9/x86_64/edge")
        self.assertEqual(loader.defines["selinux_mode"], "enforcing")
        self.assertEqual(loader.defines["selinux_policy"], "targeted")
        self.assertEqual(
            loader.defines["selinux_booleans"], ["httpd_can_network_connect=true"]
        )
        self.assertEqual(loader.defines["varpart_size"], int(1000 * 1000 * 1000 / 512))
        self.assertEqual(
            loader.defines["varpart_uuid"], "12345678-1234-1234-1234-123456789012"
        )
        self.assertEqual(loader.defines["homepart_size"], int(2000 * 1000 * 1000 / 512))

    def test_with_experimental_section(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "experimental": {
                "internal_defines": {"custom_var": "custom_value", "another_var": 42}
            },
        }
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["custom_var"], "custom_value")
        self.assertEqual(loader.defines["another_var"], 42)

    def test_default_expand(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "content": {
                "rpms": ["vim", "git", "podman"],
                "container_images": ["registry.redhat.io/ubi8/ubi:latest"],
                "systemd": {"enabled": ["sshd"], "disabled": ["firewalld"]},
            },
        }
        loader = self.load_manifest(manifest)

        self.assertEqual(loader.defines["name"], "test")
        self.assertEqual(loader.defines["version"], "1.0")

        # Should add podman to rpms due to container_images
        expected_rpms = ["vim", "git", "podman", "podman"]
        self.assertEqual(loader.defines["simple_rpms"], expected_rpms)

    def test_handle_image_invalid_size(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "image": {
                "image_size": "1GB",
                "partitions": {
                    "var": {"size": "2GB"}  # var partition larger than image
                },
            },
        }

        with self.assertRaises(exceptions.InvalidMountSize):
            self.load_manifest(manifest)

    def test_handle_image_invalid_rel_size(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "image": {
                "partitions": {"var": {"relative_size": 1.5}}  # relative size >= 1
            },
        }

        with self.assertRaises(exceptions.InvalidMountRelSize):
            self.load_manifest(manifest)

    def test_handle_image_invalid_rel_size_negative(self):
        manifest = {
            "name": "test",
            "version": "1.0",
            "image": {
                "partitions": {"var": {"relative_size": -0.5}}  # negative relative size
            },
        }

        # This should not raise an exception as negative values are allowed
        loader = self.load_manifest(manifest)
        self.assertEqual(loader.defines["varpart_relative_size"], -0.5)

    def test_set_method(self):
        """Test the set method behavior with empty values"""
        defines = {
            "_basedir": "/test",
            "_workdir": "/tmp",
            "arch": "x86_64",
            "use_fusa": False,
        }

        with patch("builtins.open", mock_open_manifest_schema()):
            loader = ManifestLoader(defines)

        # Test that empty list is not set
        loader.set("empty_list", [])
        self.assertNotIn("empty_list", loader.defines)

        # Test that empty dict is not set
        loader.set("empty_dict", {})
        self.assertNotIn("empty_dict", loader.defines)

        # Test that non-empty values are set
        loader.set("non_empty_list", ["item"])
        self.assertEqual(loader.defines["non_empty_list"], ["item"])

        loader.set("non_empty_dict", {"key": "value"})
        self.assertEqual(loader.defines["non_empty_dict"], {"key": "value"})

    def test_set_from_method(self):
        """Test the set_from method"""
        defines = {
            "_basedir": "/test",
            "_workdir": "/tmp",
            "arch": "x86_64",
            "use_fusa": False,
        }

        with patch("builtins.open", mock_open_manifest_schema()):
            loader = ManifestLoader(defines)

        # Test with existing key
        src_dict = {"existing_key": "value"}
        loader.set_from("dest_key", src_dict, "existing_key")
        self.assertEqual(loader.defines["dest_key"], "value")

        # Test with non-existing key and default
        loader.set_from("dest_key2", src_dict, "non_existing_key", "default_value")
        self.assertEqual(loader.defines["dest_key2"], "default_value")

        # Test with non-existing key and no default
        loader.set_from("dest_key3", src_dict, "non_existing_key")
        self.assertNotIn("dest_key3", loader.defines)


def mock_open_manifest_schema():
    """Mock the manifest schema file"""
    from unittest.mock import mock_open

    schema_content = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "version": {"type": "string"},
            "content": {"type": "object"},
            "qm": {"type": "object"},
            "network": {"type": "object"},
            "auth": {"type": "object"},
            "kernel": {"type": "object"},
            "image": {"type": "object"},
            "experimental": {"type": "object"},
        },
    }
    return mock_open(read_data=yaml.dump(schema_content))
