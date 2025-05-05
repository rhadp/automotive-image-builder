import unittest
from io import StringIO

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
