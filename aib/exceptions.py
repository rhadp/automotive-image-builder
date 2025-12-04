"""AIB Exceptions module"""


class AIBException(Exception):
    pass


class InvalidOption(AIBException):
    def __init__(self, option, value):
        self.option = option
        self.value = value

    def __str__(self):
        return (
            f"Invalid value passed to {self.option}: '{self.value}': "
            "should be key=value"
        )


class MissingSection(AIBException):
    def __init__(self, section):
        self.section = section

    def __str__(self):
        return f"No {self.section} section in manifest"


class DefineFileError(AIBException):
    pass


class ManifestParseError(AIBException):
    def __init__(self, manifest_path):
        self.manifest = manifest_path

    def __str__(self):
        return f"Error parsing {self.manifest}"


class SimpleManifestParseError(AIBException):
    def __init__(self, manifest_path, errors):
        self.manifest = manifest_path
        self.errors = errors

    def __str__(self):
        return f"Error parsing {self.manifest}:\n " + "\n ".join(
            e.message for e in self.errors
        )


class UnsupportedExport(AIBException):
    def __init__(self, export):
        self.export = export

    def __str__(self):
        return f"Unsupported export '{self.export}'"


class InvalidMountSize(AIBException):
    def __init__(self, mountpoint):
        self.mountpoint = mountpoint

    def __str__(self):
        return f"{self.mountpoint} can't be larger than image"


class InvalidMountRelSize(AIBException):
    def __init__(self, mountpoint):
        self.mountpoint = mountpoint

    def __str__(self):
        return f"Invalid relative size for {self.mountpoint}, must be between 0 and 1"


class NoMatchingFilesError(AIBException):
    def __init__(self, glob_pattern):
        self.glob_pattern = glob_pattern

    def __str__(self):
        return f"No files matched glob pattern: {self.glob_pattern}"


class TooManyFilesError(AIBException):
    def __init__(self, glob_pattern, matched_count, max_files):
        self.glob_pattern = glob_pattern
        self.matched_count = matched_count
        self.max_files = max_files

    def __str__(self):
        return (
            f"Glob pattern '{self.glob_pattern}' matched {self.matched_count} files, "
            f"but max_files limit is {self.max_files}. Consider using more specific "
            f"patterns or increase max_files if needed."
        )


class MissingLogFile(AIBException):
    def __str__(self):
        return "Log file must be specified when progress monitoring is enabled"


class InvalidTopLevelPath(AIBException):
    def __init__(self, path, allowed_dirs, disallowed_paths, operation_type):
        self.path = path
        self.allowed_dirs = allowed_dirs
        self.disallowed_paths = disallowed_paths
        self.operation_type = operation_type

    def __str__(self):
        return (
            f"Path '{self.path}' is not allowed for {self.operation_type}. "
            f"Files and directories must be under one of: {', '.join(self.allowed_dirs)}, "
            f"but not under {', '.join(self.disallowed_paths)}"
        )
