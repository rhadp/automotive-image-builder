import yaml
import collections


# pylint: disable=too-many-ancestors
class YamlOrderedLoader(yaml.Loader):
    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"expected a mapping node, but found {node.id}",
                node.start_mark,
            )
        mapping = collections.OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, collections.abc.Hashable):
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                )
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping

    def construct_yaml_map(self, node):
        data = collections.OrderedDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)


yaml.add_constructor("tag:yaml.org,2002:map", YamlOrderedLoader.construct_yaml_map)


def yaml_load_ordered(source):
    return yaml.load(source, YamlOrderedLoader)


def extract_comment_header(file):
    lines = []
    for line in file:
        line = line.strip()
        if line[0] != "#":
            break
        lines.append(line[1:])

    # Unindent
    min_indent = -1
    for line in lines:
        indent = 0
        for c in line:
            if c == " ":
                indent = indent + 1
            else:
                if min_indent < 0:
                    min_indent = indent
                else:
                    min_indent = min(indent, min_indent)
                break

    if min_indent > 0:
        for i in range(len(lines)):
            lines[i] = lines[i][min_indent:]

    # Remove trailing empty lines
    while len(lines) > 0 and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def get_osbuild_major_version(runner, use_container):
    osbuild_version = runner.run(
        ["/usr/bin/osbuild", "--version"],
        use_container=use_container,
        capture_output=True,
    )
    osbuild_major_version = osbuild_version.split()[-1].split(".")[0]

    return int(osbuild_major_version)
