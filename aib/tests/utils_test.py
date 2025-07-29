import unittest
from io import StringIO
from unittest.mock import Mock

from aib import utils


class TestExtractCommentsHeader(unittest.TestCase):
    def test_extract_comment_header(self):
        data = """# foo bar
        some other text
        """

        res = utils.extract_comment_header(StringIO(data))
        self.assertEqual(res, "foo bar")

        data = """# more
        # foobar
        some other text
        """

        res = utils.extract_comment_header(StringIO(data))
        self.assertEqual(res, "more\nfoobar")

        data = """# foo
        #  indented
        some other text
        """

        res = utils.extract_comment_header(StringIO(data))
        self.assertEqual(res, "foo\n indented")

        data = """#empty lines
        #
        #
        some other text
        """
        res = utils.extract_comment_header(StringIO(data))
        self.assertEqual(res, "empty lines")

    def test_extract_comment_header_edge_cases(self):
        """Test edge cases for extract_comment_header"""
        # Empty file
        data = ""
        res = utils.extract_comment_header(StringIO(data))
        self.assertEqual(res, "")

        # No comments
        data = "just regular text"
        res = utils.extract_comment_header(StringIO(data))
        self.assertEqual(res, "")

        # Comments with no indentation
        data = """#comment1
#comment2
regular text
"""
        res = utils.extract_comment_header(StringIO(data))
        self.assertEqual(res, "comment1\ncomment2")


class TestGetOsbuildMajorVersion(unittest.TestCase):
    def test_get_osbuild_major_version(self):
        """Test get_osbuild_major_version function"""
        mock_runner = Mock()
        mock_runner.run.return_value = "osbuild 1.7.5"

        result = utils.get_osbuild_major_version(mock_runner, use_container=True)

        self.assertEqual(result, 1)
        mock_runner.run.assert_called_once_with(
            ["/usr/bin/osbuild", "--version"],
            use_container=True,
            capture_output=True,
        )

    def test_get_osbuild_major_version_different_versions(self):
        """Test get_osbuild_major_version with different version formats"""
        mock_runner = Mock()

        # Test version 2.x
        mock_runner.run.return_value = "osbuild 2.4.0"
        result = utils.get_osbuild_major_version(mock_runner, use_container=False)
        self.assertEqual(result, 2)

        # Test version 3.x
        mock_runner.run.return_value = "osbuild 3.0.1"
        result = utils.get_osbuild_major_version(mock_runner, use_container=True)
        self.assertEqual(result, 3)

    def test_get_osbuild_major_version_container_param(self):
        """Test that use_container parameter is passed correctly"""
        mock_runner = Mock()
        mock_runner.run.return_value = "osbuild 1.7.5"

        # Test with use_container=False
        utils.get_osbuild_major_version(mock_runner, use_container=False)
        mock_runner.run.assert_called_with(
            ["/usr/bin/osbuild", "--version"],
            use_container=False,
            capture_output=True,
        )

        # Test with use_container=True
        utils.get_osbuild_major_version(mock_runner, use_container=True)
        mock_runner.run.assert_called_with(
            ["/usr/bin/osbuild", "--version"],
            use_container=True,
            capture_output=True,
        )
