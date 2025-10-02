import unittest
import os
import tempfile
from unittest.mock import Mock, patch

from aib.exports import get_export_data, export, EXPORT_DATAS
from aib.exceptions import UnsupportedExport


class TestGetExportData(unittest.TestCase):
    def test_get_export_data_valid_exports(self):
        """Test get_export_data with valid export types"""
        # Test a few common export types
        qcow2_data = get_export_data("qcow2")
        self.assertEqual(qcow2_data["desc"], "Disk image in qcow2 format")
        self.assertEqual(qcow2_data["filename"], "disk.qcow2")

        image_data = get_export_data("image")
        self.assertEqual(image_data["desc"], "Raw disk image")
        self.assertEqual(image_data["filename"], "disk.img")

        ostree_data = get_export_data("ostree-commit")
        self.assertEqual(ostree_data["desc"], "OSTree repo containing a commit")
        self.assertEqual(ostree_data["filename"], "repo")
        self.assertTrue(ostree_data["is_dir"])

    def test_get_export_data_with_export_arg(self):
        """Test export types that have export_arg"""
        bootc_data = get_export_data("bootc")
        self.assertEqual(bootc_data["export_arg"], "bootc-archive")
        self.assertEqual(bootc_data["convert"], "podman-import")

        simg_data = get_export_data("simg")
        self.assertEqual(simg_data["export_arg"], "image")
        self.assertEqual(simg_data["convert"], "simg")

    def test_get_export_data_unsupported_export(self):
        """Test get_export_data with unsupported export type"""
        with self.assertRaises(UnsupportedExport) as cm:
            get_export_data("unsupported-export")
        self.assertEqual(str(cm.exception), "Unsupported export 'unsupported-export'")

    def test_get_export_data_all_exports(self):
        """Test that all defined exports in EXPORT_DATAS are accessible"""
        for export_type in EXPORT_DATAS.keys():
            data = get_export_data(export_type)
            self.assertIsInstance(data, dict)
            self.assertIn("desc", data)


class TestExport(unittest.TestCase):
    def setUp(self):
        self.mock_runner = Mock()
        self.tmpdir = tempfile.mkdtemp()
        self.outputdir = os.path.join(self.tmpdir, "output")
        os.makedirs(self.outputdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_basic_file(self):
        """Test basic file export without conversion"""
        # Create a test export directory and file
        export_dir = os.path.join(self.outputdir, "qcow2")
        os.makedirs(export_dir)
        test_file = os.path.join(export_dir, "disk.qcow2")
        with open(test_file, "w") as f:
            f.write("test content")

        dest = os.path.join(self.tmpdir, "output.qcow2")

        export(self.outputdir, dest, False, "qcow2", self.mock_runner)

        # Should call chown and mv
        self.mock_runner.run_as_root.assert_any_call(
            ["chown", f"{os.getuid()}:{os.getgid()}", test_file]
        )
        self.mock_runner.run_as_root.assert_any_call(["mv", test_file, dest])

    def test_export_directory_destination(self):
        """Test export to directory destination"""
        # Create a test export directory and file
        export_dir = os.path.join(self.outputdir, "image")
        os.makedirs(export_dir)
        test_file = os.path.join(export_dir, "disk.img")
        with open(test_file, "w") as f:
            f.write("test content")

        dest_dir = os.path.join(self.tmpdir, "dest")
        os.makedirs(dest_dir)

        export(self.outputdir, dest_dir, True, "image", self.mock_runner)

        expected_dest = os.path.join(dest_dir, "disk.img")
        self.mock_runner.run_as_root.assert_any_call(["mv", test_file, expected_dest])

    def test_export_directory_type(self):
        """Test export of directory type (like ostree-commit)"""
        # Create a test export directory
        export_dir = os.path.join(self.outputdir, "ostree-commit")
        repo_dir = os.path.join(export_dir, "repo")
        os.makedirs(repo_dir)

        dest = os.path.join(self.tmpdir, "repo")

        with patch("os.path.isdir", return_value=True):
            export(self.outputdir, dest, False, "ostree-commit", self.mock_runner)

        # Should remove existing destination for directory exports
        self.mock_runner.run_as_root.assert_any_call(["rm", "-rf", dest])
        # Should move the directory
        self.mock_runner.run_as_root.assert_any_call(["mv", repo_dir, dest])

    def test_export_with_export_arg(self):
        """Test export with export_arg (like bootc -> bootc-archive)"""
        # Create a test export directory and file for bootc-archive
        export_dir = os.path.join(self.outputdir, "bootc-archive")
        os.makedirs(export_dir)
        test_file = os.path.join(export_dir, "image.oci-archive")
        with open(test_file, "w") as f:
            f.write("test content")

        dest = os.path.join(self.tmpdir, "output.oci-archive")

        export(self.outputdir, dest, False, "bootc", self.mock_runner)

        # Should call skopeo for podman-import conversion
        self.mock_runner.run_as_root.assert_any_call(
            [
                "skopeo",
                "copy",
                "--quiet",
                "oci-archive:" + test_file,
                "containers-storage:" + dest,
            ]
        )

    def test_export_simg_conversion(self):
        """Test export with simg conversion"""
        # Create a test export directory and file
        export_dir = os.path.join(self.outputdir, "image")
        os.makedirs(export_dir)
        test_file = os.path.join(export_dir, "disk.img")
        with open(test_file, "w") as f:
            f.write("test content")

        dest = os.path.join(self.tmpdir, "output.simg")

        export(self.outputdir, dest, False, "simg", self.mock_runner)

        # Should call img2simg for conversion
        converted_file = os.path.splitext(test_file)[0] + ".simg"
        self.mock_runner.run_in_container.assert_any_call(
            ["img2simg", test_file, converted_file]
        )
        # Should remove original file
        self.mock_runner.run_as_root.assert_any_call(["rm", "-rf", test_file])

    def test_export_simg_conversion_with_convert_filename(self):
        """Test export with simg conversion using convert_filename pattern"""
        # Create a test export directory with multiple files
        export_dir = os.path.join(self.outputdir, "aboot")
        images_dir = os.path.join(export_dir, "images")
        os.makedirs(images_dir)

        # Create test files matching the pattern
        test_file1 = os.path.join(images_dir, "boot.ext4")
        test_file2 = os.path.join(images_dir, "system.ext4")
        with open(test_file1, "w") as f:
            f.write("boot content")
        with open(test_file2, "w") as f:
            f.write("system content")

        dest = os.path.join(self.tmpdir, "output_images")

        export(self.outputdir, dest, False, "aboot.simg", self.mock_runner)

        # Should call img2simg for each .ext4 file
        converted_file1 = os.path.splitext(test_file1)[0] + ".simg"
        converted_file2 = os.path.splitext(test_file2)[0] + ".simg"

        self.mock_runner.run_in_container.assert_any_call(
            ["img2simg", test_file1, converted_file1]
        )
        self.mock_runner.run_in_container.assert_any_call(
            ["img2simg", test_file2, converted_file2]
        )

    def test_export_no_chown_flag(self):
        """Test export with no_chown flag (like rootfs)"""
        # Create a test export directory
        export_dir = os.path.join(self.outputdir, "rootfs")
        os.makedirs(export_dir)

        dest = os.path.join(self.tmpdir, "rootfs_output")

        export(self.outputdir, dest, False, "rootfs", self.mock_runner)

        # Should not call chown for rootfs export
        chown_calls = [
            call
            for call in self.mock_runner.run.call_args_list
            if call[0][0][0] == "chown"
        ]
        self.assertEqual(len(chown_calls), 0)

    def test_export_no_filename(self):
        """Test export where filename is None (like rootfs)"""
        # Create a test export directory
        export_dir = os.path.join(self.outputdir, "rootfs")
        os.makedirs(export_dir)

        dest = os.path.join(self.tmpdir, "rootfs_output")

        export(self.outputdir, dest, False, "rootfs", self.mock_runner)

        # Should move the export directory itself
        self.mock_runner.run_as_root.assert_any_call(["mv", export_dir, dest])

    @patch("os.path.isfile")
    def test_export_removes_existing_directory_destination(self, mock_isfile):
        """Test that existing destination is removed for directory exports"""
        mock_isfile.return_value = True

        # Create a test export directory
        export_dir = os.path.join(self.outputdir, "ostree-commit")
        repo_dir = os.path.join(export_dir, "repo")
        os.makedirs(repo_dir)

        dest = os.path.join(self.tmpdir, "repo")

        export(self.outputdir, dest, False, "ostree-commit", self.mock_runner)

        # Should remove existing destination
        self.mock_runner.run_as_root.assert_any_call(["rm", "-rf", dest])

    def test_export_unsupported_type(self):
        """Test export with unsupported export type"""
        with self.assertRaises(UnsupportedExport):
            export(self.outputdir, "dest", False, "unsupported", self.mock_runner)
