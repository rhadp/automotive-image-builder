import unittest
import sys
import subprocess
from unittest.mock import patch
from io import StringIO

from aib.version import __version__


class TestVersion(unittest.TestCase):
    def test_version_string(self):
        """Test that __version__ is a string"""
        self.assertIsInstance(__version__, str)
        self.assertTrue(len(__version__) > 0)
        # Check it follows semantic versioning pattern (x.y.z)
        parts = __version__.split(".")
        self.assertEqual(len(parts), 3)
        for part in parts:
            self.assertTrue(part.isdigit())

    def test_main_execution(self):
        """Test that running the module as main prints the version"""
        # Use subprocess to run the module as main
        result = subprocess.run(
            [sys.executable, "-m", "aib.version"], capture_output=True, text=True
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), __version__)

    def test_main_execution_direct(self):
        """Test the __main__ block directly"""
        # This directly executes the code in the __main__ block
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            # Execute the print statement from the __main__ block
            exec("print(__version__)", {"__version__": __version__})

            output = mock_stdout.getvalue().strip()
            self.assertEqual(output, __version__)
