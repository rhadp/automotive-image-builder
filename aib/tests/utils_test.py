import os
import tempfile
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
        mock_runner.run_as_user.return_value = "osbuild 1.7.5"

        result = utils.get_osbuild_major_version(mock_runner, use_container=True)

        self.assertEqual(result, 1)
        mock_runner.run_as_user.assert_called_once_with(
            ["/usr/bin/osbuild", "--version"],
            capture_output=True,
        )

    def test_get_osbuild_major_version_different_versions(self):
        """Test get_osbuild_major_version with different version formats"""
        mock_runner = Mock()

        # Test version 2.x
        mock_runner.run_as_user.return_value = "osbuild 2.4.0"
        result = utils.get_osbuild_major_version(mock_runner, use_container=False)
        self.assertEqual(result, 2)

        # Test version 3.x
        mock_runner.run_as_user.return_value = "osbuild 3.0.1"
        result = utils.get_osbuild_major_version(mock_runner, use_container=True)
        self.assertEqual(result, 3)

    def test_get_osbuild_major_version_container_param(self):
        """Test that use_container parameter is passed correctly"""
        mock_runner = Mock()
        mock_runner.run_as_user.return_value = "osbuild 1.7.5"

        # Test with use_container=False
        utils.get_osbuild_major_version(mock_runner, use_container=False)
        mock_runner.run_as_user.assert_called_with(
            ["/usr/bin/osbuild", "--version"],
            capture_output=True,
        )

        # Test with use_container=True
        utils.get_osbuild_major_version(mock_runner, use_container=True)
        mock_runner.run_as_user.assert_called_with(
            ["/usr/bin/osbuild", "--version"],
            capture_output=True,
        )


class TestCountTrailingZeros(unittest.TestCase):
    """Tests for count_trailing_zeros function."""

    def test_no_trailing_zeros(self):
        """Test with no trailing zeros."""
        self.assertEqual(utils.count_trailing_zeros(b"hello"), 0)
        self.assertEqual(utils.count_trailing_zeros(b"\x01\x02\x03"), 0)

    def test_all_zeros(self):
        """Test with all zeros."""
        self.assertEqual(utils.count_trailing_zeros(b"\x00\x00\x00"), 3)
        self.assertEqual(utils.count_trailing_zeros(b"\x00" * 100), 100)

    def test_some_trailing_zeros(self):
        """Test with some trailing zeros."""
        self.assertEqual(utils.count_trailing_zeros(b"hello\x00\x00\x00"), 3)
        self.assertEqual(utils.count_trailing_zeros(b"\x01\x02\x00"), 1)
        self.assertEqual(utils.count_trailing_zeros(b"data\x00" * 10), 1)

    def test_empty_bytes(self):
        """Test with empty bytes."""
        self.assertEqual(utils.count_trailing_zeros(b""), 0)

    def test_single_byte(self):
        """Test with single byte."""
        self.assertEqual(utils.count_trailing_zeros(b"\x00"), 1)
        self.assertEqual(utils.count_trailing_zeros(b"\x01"), 0)

    def test_zeros_in_middle(self):
        """Zeros in middle should not be counted."""
        self.assertEqual(utils.count_trailing_zeros(b"hello\x00\x00world"), 0)
        self.assertEqual(utils.count_trailing_zeros(b"\x00\x00\x01\x00\x00"), 2)


class TestRoundup(unittest.TestCase):
    """Tests for roundup function."""

    def test_already_aligned(self):
        """Test numbers already aligned to block size."""
        self.assertEqual(utils.roundup(512, 512), 512)
        self.assertEqual(utils.roundup(1024, 512), 1024)
        self.assertEqual(utils.roundup(0, 512), 0)

    def test_needs_rounding(self):
        """Test numbers that need rounding up."""
        self.assertEqual(utils.roundup(100, 512), 512)
        self.assertEqual(utils.roundup(513, 512), 1024)
        self.assertEqual(utils.roundup(1000, 512), 1024)
        self.assertEqual(utils.roundup(1, 512), 512)

    def test_different_block_sizes(self):
        """Test with various block sizes."""
        self.assertEqual(utils.roundup(100, 1), 100)
        self.assertEqual(utils.roundup(100, 10), 100)
        self.assertEqual(utils.roundup(101, 10), 110)
        self.assertEqual(utils.roundup(100, 4096), 4096)
        self.assertEqual(utils.roundup(4097, 4096), 8192)

    def test_zero_block_causes_error(self):
        """Test that zero block size causes division by zero."""
        # This exposes bug #2 - currently crashes instead of raising proper error
        with self.assertRaises(ZeroDivisionError):
            utils.roundup(100, 0)


class TestZeroTailSize(unittest.TestCase):
    """Tests for zero_tail_size function."""

    def test_no_trailing_zeros(self):
        """Test file with no trailing zeros."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            f.flush()
            fname = f.name

        try:
            result = utils.zero_tail_size(fname, 0, 11)
            self.assertEqual(result, 0)
        finally:
            os.unlink(fname)

    def test_all_zeros(self):
        """Test file that is all zeros."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x00" * 1000)
            f.flush()
            fname = f.name

        try:
            result = utils.zero_tail_size(fname, 0, 1000)
            self.assertEqual(result, 1000)
        finally:
            os.unlink(fname)

    def test_some_trailing_zeros(self):
        """Test file with some trailing zeros."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"data" + b"\x00" * 100)
            f.flush()
            fname = f.name

        try:
            result = utils.zero_tail_size(fname, 0, 104)
            self.assertEqual(result, 100)
        finally:
            os.unlink(fname)

    def test_with_offset(self):
        """Test reading from offset in file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"prefix" + b"data" + b"\x00" * 50)
            f.flush()
            fname = f.name

        try:
            # Read from offset 6, skipping "prefix"
            result = utils.zero_tail_size(fname, 6, 54)
            self.assertEqual(result, 50)
        finally:
            os.unlink(fname)

    def test_past_eof_counts_as_zeros(self):
        """Test that bytes past EOF are treated as zeros."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            f.flush()
            fname = f.name

        try:
            # Request 100 bytes when file only has 5
            # Bytes 5-99 should be considered zeros
            result = utils.zero_tail_size(fname, 0, 100)
            self.assertEqual(result, 95)
        finally:
            os.unlink(fname)

    def test_with_small_chunk_size(self):
        """Test with small chunk size to test chunking logic."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 100 + b"\x00" * 100)
            f.flush()
            fname = f.name

        try:
            # Use small chunk to force multiple reads
            result = utils.zero_tail_size(fname, 0, 200, chunk_size=10)
            self.assertEqual(result, 100)
        finally:
            os.unlink(fname)

    def test_empty_range(self):
        """Test with zero-size range."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            f.flush()
            fname = f.name

        try:
            result = utils.zero_tail_size(fname, 0, 0)
            self.assertEqual(result, 0)
        finally:
            os.unlink(fname)


class TestExtractPartOfFile(unittest.TestCase):
    """Tests for extract_part_of_file function."""

    def setUp(self):
        """Set up temporary directory for tests."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_basic_extraction(self):
        """Test basic file extraction."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        with open(src, "wb") as f:
            f.write(b"hello world")

        written = utils.extract_part_of_file(src, dst, 0, 11)

        self.assertEqual(written, 11)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), b"hello world")

    def test_extract_with_offset(self):
        """Test extraction starting at offset."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        with open(src, "wb") as f:
            f.write(b"prefix:data:suffix")

        # Extract just "data" (bytes 7-11)
        written = utils.extract_part_of_file(src, dst, 7, 4)

        self.assertEqual(written, 4)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), b"data")

    def test_extract_with_chunking(self):
        """Test extraction with small chunk size."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        data = b"x" * 1000
        with open(src, "wb") as f:
            f.write(data)

        # Use small chunk size to test chunking
        written = utils.extract_part_of_file(src, dst, 0, 1000, chunk_size=100)

        self.assertEqual(written, 1000)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), data)

    def test_extract_past_eof(self):
        """Test extraction when size extends past EOF."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        with open(src, "wb") as f:
            f.write(b"hello")

        # Request 100 bytes but file only has 5
        written = utils.extract_part_of_file(src, dst, 0, 100)

        # Should only write what's available
        self.assertEqual(written, 5)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), b"hello")

    def test_skip_zero_tail_basic(self):
        """Test skipping trailing zeros."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        # Data with trailing zeros
        with open(src, "wb") as f:
            f.write(b"data" + b"\x00" * 600)

        written = utils.extract_part_of_file(
            src, dst, 0, 604, skip_zero_tail=True, skip_zero_block_size=512
        )

        # Should write "data" rounded up to 512 bytes
        self.assertEqual(written, 512)
        with open(dst, "rb") as f:
            result = f.read()
            self.assertEqual(result[:4], b"data")
            self.assertEqual(len(result), 512)

    def test_skip_zero_tail_exact_block(self):
        """Test skip_zero_tail when data is exactly block-aligned."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        # Exactly 512 bytes data + zeros
        with open(src, "wb") as f:
            f.write(b"x" * 512 + b"\x00" * 500)

        written = utils.extract_part_of_file(
            src, dst, 0, 1012, skip_zero_tail=True, skip_zero_block_size=512
        )

        self.assertEqual(written, 512)
        with open(dst, "rb") as f:
            self.assertEqual(len(f.read()), 512)

    def test_empty_file_extraction(self):
        """Test extracting from empty file."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        with open(src, "wb") as f:
            pass  # Empty file

        written = utils.extract_part_of_file(src, dst, 0, 0)

        self.assertEqual(written, 0)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), b"")

    def test_extract_zero_bytes(self):
        """Test requesting zero bytes."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        with open(src, "wb") as f:
            f.write(b"hello world")

        written = utils.extract_part_of_file(src, dst, 5, 0)

        self.assertEqual(written, 0)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), b"")

    def test_overwrite_existing_file(self):
        """Test that existing destination file is overwritten."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        with open(src, "wb") as f:
            f.write(b"new data")

        with open(dst, "wb") as f:
            f.write(b"old data that should be replaced")

        written = utils.extract_part_of_file(src, dst, 0, 8)

        self.assertEqual(written, 8)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), b"new data")

    def test_large_file_extraction(self):
        """Test extracting large file to verify chunking works."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        # Create 10MB file
        size = 10 * 1024 * 1024
        chunk = b"A" * (1024 * 1024)

        with open(src, "wb") as f:
            for _ in range(10):
                f.write(chunk)

        written = utils.extract_part_of_file(src, dst, 0, size)

        self.assertEqual(written, size)
        self.assertEqual(os.path.getsize(dst), size)

    def test_extract_middle_of_large_file(self):
        """Test extracting from middle of large file."""
        src = os.path.join(self.test_dir, "source.bin")
        dst = os.path.join(self.test_dir, "dest.bin")

        # Create file with identifiable sections
        with open(src, "wb") as f:
            f.write(b"A" * 1000 + b"B" * 1000 + b"C" * 1000)

        # Extract middle section (the B's)
        written = utils.extract_part_of_file(src, dst, 1000, 1000)

        self.assertEqual(written, 1000)
        with open(dst, "rb") as f:
            self.assertEqual(f.read(), b"B" * 1000)
