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
    osbuild_version = runner.run_as_user(
        ["/usr/bin/osbuild", "--version"],
        capture_output=True,
    )
    osbuild_major_version = osbuild_version.split()[-1].split(".")[0]

    return int(osbuild_major_version)
