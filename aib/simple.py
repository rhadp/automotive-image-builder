#!/usr/bin/env python3

import os
import yaml
import re

import jsonschema

from . import exceptions


# Duplicate a dict and drop one key
def without(d, key):
    new_d = d.copy()
    new_d.pop(key)
    return new_d


def parse_size(s: str):
    """Parse a size string into a number.

    Supported suffixes: kB, kiB, MB, MiB, GB, GiB, TB, TiB
    """
    units = [
        (r"^\s*(\d+)\s*kB$", 1000, 1),
        (r"^\s*(\d+)\s*KiB$", 1024, 1),
        (r"^\s*(\d+)\s*MB$", 1000, 2),
        (r"^\s*(\d+)\s*MiB$", 1024, 2),
        (r"^\s*(\d+)\s*GB$", 1000, 3),
        (r"^\s*(\d+)\s*GiB$", 1024, 3),
        (r"^\s*(\d+)\s*TB$", 1000, 4),
        (r"^\s*(\d+)\s*TiB$", 1024, 4),
        (r"^\s*(\d+)$", 1, 1),
    ]

    for pat, base, power in units:
        m = re.fullmatch(pat, s)
        if m:
            if isinstance(base, int):
                return int(m.group(1)) * base**power

    raise TypeError(f"invalid size value: '{s}'")


# Convert a python value to 'true' or 'false'
def json_bool(b):
    if b:
        return "true"
    return "false"


# The manifest we use is always empty.mpp.yml, but due to who the
# osbuil-mpp syntax and evaluation works we need to also generate an
# extra manifest with the included file content. This is shared betwee
# the QM and the Rootfs partition
class ExtraInclude:
    def __init__(self, basedir):
        self.basedir = os.path.abspath(basedir)
        self.content_id = 1
        self.file_content_inputs = {}
        self.file_content_paths = []

    def gen_id(self):
        content_id = self.content_id
        self.content_id = content_id + 1
        return content_id

    def gen_file_input(self, content_id, data):
        mpp_embed = {
            "id": "image_content_id_" + str(content_id),
        }
        if "text" in data:
            mpp_embed["text"] = data["text"]
        if "url" in data:
            mpp_embed["url"] = data["url"]
        if "source_path" in data:
            path = data["source_path"]
            if not os.path.isabs(path):
                path = os.path.normpath(os.path.join(self.basedir, path))
            mpp_embed["path"] = path
        return {
            "type": "org.osbuild.files",
            "origin": "org.osbuild.source",
            "mpp-embed": mpp_embed,
        }

    def gen_file_copy(self, content_id):
        return {
            "from": {
                "mpp-format-string": "input://inlinefile"
                + str(content_id)
                + "/{embedded['image_content_id_"
                + str(content_id)
                + "']}"
            },
            "to": "tree:///image_content_" + str(content_id),
        }

    def gen_file_copy_out(self, content_id, data):
        return {
            "from": "input://extra/image_content_" + str(content_id),
            "to": "tree://" + data["path"],
        }

    def add_file_copy(self, contents, data):
        content_id = self.gen_id()
        self.file_content_inputs["inlinefile" + str(content_id)] = self.gen_file_input(
            content_id, data
        )
        self.file_content_paths.append(self.gen_file_copy(content_id))
        contents.file_content_copy.append(self.gen_file_copy_out(content_id, data))

    def generate(self):
        extra_include_pipelines = []
        file_content_stages = []

        if self.file_content_inputs:
            file_content_stages.append(
                {
                    "type": "org.osbuild.copy",
                    "inputs": self.file_content_inputs,
                    "options": {"paths": self.file_content_paths},
                }
            )

        if file_content_stages:
            extra_include_pipelines.append(
                {"name": "extra-image-content", "stages": file_content_stages}
            )

        return {"version": "2", "pipelines": extra_include_pipelines}


# Both the rootfs and qm partition contents are specified with the same
# syntax, but use slightly different mpp variables, to share this code
# we have one class (Contents) for the rootfs one and override some details
# in the QMContents class.
class Contents:
    def __init__(self, loader, data, extra_include):
        self.loader = loader
        self.extra_include = extra_include

        self.enable_repos = data.get("enable_repos", [])
        self.repos = data.get("repos", [])
        self.rpms = data.get("rpms", [])
        self.containers = data.get("container_images", [])
        self.add_files = data.get("add_files", [])
        self.chown_files = data.get("chown_files", [])
        self.chmod_files = data.get("chmod_files", [])
        self.remove_files = data.get("remove_files", [])
        self.make_dirs = data.get("make_dirs", [])
        self.file_content_copy = []
        self.systemd = data.get("systemd", {})
        self.sbom = data.get("sbom", {})

    # Gets key to use for target partition (rootfs/qm)
    def get_key(self, key):
        return key

    # Sets different key depending on target partition
    def set_define(self, key, value):
        key = self.get_key(key)
        self.loader.set(key, value)

    def set_defines(self):
        for file in self.add_files:
            self.extra_include.add_file_copy(self, file)
        self.set_define("simple_copy", self.file_content_copy)

        self.set_define("simple_mkdir", self.make_dirs)

        chmod_files = {f["path"]: without(f, "path") for f in self.chmod_files}
        self.set_define("simple_chmod", chmod_files)

        chown_files = {f["path"]: without(f, "path") for f in self.chown_files}
        self.set_define("simple_chown", chown_files)

        simple_remove = []
        for remove in self.remove_files:
            simple_remove.append(remove["path"])
        self.set_define("simple_remove", simple_remove)

        for r in self.repos:
            url = r["baseurl"]
            r["baseurl"] = url.replace("$arch", self.loader.defines["arch"])

        if "debug" in self.enable_repos:
            self.set_define("simple_add_debug_repos", True)
        if "devel" in self.enable_repos:
            self.set_define("simple_add_devel_repos", True)

        # If we have containers, always add podman rpm
        if self.containers:
            self.rpms.append("podman")

        self.set_define("simple_repos", self.repos)
        self.set_define("simple_rpms", self.rpms)

        self.set_define("simple_containers", self.containers)
        if self.containers:
            self.set_define("use_containers_extra_store", True)

        if self.systemd:
            self.set_define("simple_systemd", self.systemd)

        if self.sbom:
            self.set_define("simple_sbom", self.sbom)


class QMContents(Contents):
    def __init__(self, loader, data, extra_include):
        Contents.__init__(self, loader, data, extra_include)

    def get_key(self, key):
        if key.startswith("use_"):
            return "use_qm_" + key[4:]
        return "qm_" + key

    def set_defines(self):
        Contents.set_defines(self)


def validateNoFusa(validator, noFusa, instance, _schema):
    # For objects, noFusa means we disallow the named properties
    if validator.is_type(instance, "object"):
        for prop in noFusa:
            if prop in instance:
                message = (
                    f"With --fusa, property '{prop}' is not allowed in {instance!r}"
                )
                yield jsonschema.ValidationError(message)

    # For values, noFusa means we don't allow any of the listed values
    if validator.is_type(instance, "string") or validator.is_type(instance, "number"):
        for value in noFusa:
            if instance == value:
                message = (
                    f"With --fusa, value '{value}'  is not allowed in {instance!r}"
                )
                yield jsonschema.ValidationError(message)


def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if isinstance(subschema, dict) and "default" in subschema:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(validator, properties, instance, schema):
            yield error

    return jsonschema.validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


class ManifestLoader:
    def __init__(self, defines):
        self.aib_basedir = defines["_basedir"]
        self.workdir = defines["_workdir"]
        self.defines = defines
        fusa = defines["use_fusa"]

        # Note: Draft7 is what osbuild uses, and is available in rhel9
        base_cls = jsonschema.Draft7Validator
        validator_cls = base_cls
        if fusa:
            validator_cls = jsonschema.validators.extend(
                base_cls,
                validators={
                    "noFusa": validateNoFusa,
                },
            )
        validator_cls = extend_with_default(validator_cls)

        with open(
            os.path.join(self.aib_basedir, "files/manifest_schema.yml"),
            mode="r",
        ) as file:
            self.aib_schema = yaml.load(file, yaml.SafeLoader)
            base_cls.check_schema(self.aib_schema)

        self.validator = validator_cls(self.aib_schema)

    def set(self, key, value):
        if (isinstance(value, list) or isinstance(value, dict)) and len(value) == 0:
            return
        self.defines[key] = value

    def set_from(self, key, src_dict, src_key, default=None):
        if src_key in src_dict:
            self.set(key, src_dict[src_key])
        elif default is not None:
            self.set(key, default)

    def handle_qm(self, qm, extra_include):
        self.set("use_qm", True)
        if "content" in qm:
            qm_content = QMContents(self, qm["content"], extra_include)
            qm_content.set_defines()

        memory_limit = qm.get("memory_limit", {})
        self.set_from("qm_memory_max", memory_limit, "max")
        self.set_from("qm_memory_high", memory_limit, "high")

        self.set_from("qm_cpu_weight", qm, "cpu_weight")
        self.set_from("boot_check_qm_digest", qm, "container_checksum")

    def handle_network(self, network):
        static = network.get("static", {})
        if static:
            self.set("use_static_ip", True)
            self.set_from("static_ip", static, "ip")
            ip_prefixlen = static["ip_prefixlen"]
            if ip_prefixlen:
                self.set("static_ip_prefixlen", str(ip_prefixlen))
            self.set_from("static_gw", static, "gateway")
            self.set_from("static_dns", static, "dns")
            self.set_from("static_ip_iface", static, "iface")
            if "load_module" in static:
                self.set("static_ip_modules", [static["load_module"]])

    def handle_auth(self, auth):
        # Always override to disable by default
        self.set_from("root_password", auth, "root_password", "")
        self.set_from("root_ssh_keys", auth, "root_ssh_keys")
        self.set_from("simple_sshd_config", auth, "sshd_config")
        self.set_from("simple_groups", auth, "groups")
        self.set_from("simple_users", auth, "users")

    def handle_kernel(self, kernel):
        self.set_from("kernel_package", kernel, "kernel_package")
        self.set_from("kernel_version", kernel, "kernel_version")
        self.set_from("kernel_loglevel", kernel, "loglevel")
        self.set_from("use_debug", kernel, "debug_logging")
        self.set_from("simple_kernel_opts", kernel, "cmdline")
        self.set_from("denylist_modules", kernel, "remove_modules")

    def handle_image(self, image):
        image_size = image.get("image_size")
        if image_size:
            image_size = parse_size(image_size)
            self.set("image_size", str(image_size))
        partitions = image.get("partitions", {})
        for k in partitions:
            part = partitions[k]
            if k in ["var", "var_qm"]:
                if k == "var":
                    prefix = ""
                    mountpoint = "/var"
                else:
                    prefix = "qm_"
                    mountpoint = "/var/qm"

                if "size" in part:
                    var_size = part.get("size")
                    var_size = parse_size(var_size)
                    if image_size and var_size >= image_size:
                        raise exceptions.InvalidMountSize(mountpoint)
                    self.set(prefix + "varpart_size", int(var_size / 512))
                elif "relative_size" in part:
                    rel_var_size = part.get("relative_size")
                    if rel_var_size >= 1:
                        raise exceptions.InvalidMountRelSize(mountpoint)
                    self.set(prefix + "varpart_relative_size", rel_var_size)
                elif "external" in part and part["external"]:
                    self.set(prefix + "varpart_size", -1)

                if "uuid" in part:
                    self.set(prefix + "varpart_uuid", part.get("uuid"))

            else:  # Non /var
                if "size" in part:
                    part_size = parse_size(part["size"])
                    self.set(k + "part_size", int(part_size / 512))
        self.set_from("hostname", image, "hostname")
        self.set_from("ostree_ref", image, "ostree_ref")
        self.set_from("selinux_mode", image, "selinux_mode")
        self.set_from("selinux_policy", image, "selinux_policy")
        bools = image.get("selinux_booleans", {})
        if len(bools) > 0:
            self.set(
                "selinux_booleans", [f"{k}={json_bool(v)}" for (k, v) in bools.items()]
            )

    def handle_experimental(self, experimental):
        internal_defines = experimental.get("internal_defines", {})
        for k in internal_defines:
            self.set(k, internal_defines[k])

    def load(self, path, manifest_basedir):
        with open(path, mode="r") as f:
            try:
                manifest = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise exceptions.ManifestParseError(manifest_basedir) from exc

        self._load(manifest, path, manifest_basedir)

    def _load(self, manifest, path, manifest_basedir):
        errors = sorted(self.validator.iter_errors(manifest), key=lambda e: e.path)
        if errors:
            raise exceptions.SimpleManifestParseError(path, errors)

        # Extra include snippet for content, shared between contents
        extra_include = ExtraInclude(manifest_basedir)

        self.set_from("name", manifest, "name")
        self.set_from("version", manifest, "version")

        content = Contents(self, manifest.get("content", {}), extra_include)
        content.set_defines()

        if "qm" in manifest:
            self.handle_qm(manifest["qm"], extra_include)

        self.handle_network(manifest.get("network", {}))
        self.handle_auth(manifest.get("auth", {}))
        self.handle_kernel(manifest.get("kernel", {}))
        self.handle_image(manifest.get("image", {}))
        self.handle_experimental(manifest.get("experimental", {}))

        # Write out extra_include mpp file for file content
        extra_include_path = os.path.join(self.workdir, "extra-include.ipp.yml")
        with open(extra_include_path, "w") as f:
            yaml.dump(extra_include.generate(), f, sort_keys=False)
        self.set("simple_import", extra_include_path)
