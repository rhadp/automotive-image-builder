import unittest
from unittest.mock import Mock, patch
from aib.progress import (
    OSBuildProgressMonitor,
    ProgressStep,
    ProgressArgs,
    NestedProgressInfo,
    StageEventInfo,
)


class TestProgressStep(unittest.TestCase):
    def test_progress_step_creation(self):
        """Test ProgressStep dataclass creation."""
        # Test with default values
        step = ProgressStep()
        self.assertEqual(step.name, "")
        self.assertEqual(step.total, 0)
        self.assertEqual(step.done, 0)

        # Test with custom values
        step = ProgressStep(name="test", total=100, done=50)
        self.assertEqual(step.name, "test")
        self.assertEqual(step.total, 100)
        self.assertEqual(step.done, 50)

    def test_progress_step_percentage(self):
        """Test ProgressStep percentage calculation."""
        # Normal case
        step = ProgressStep(total=100, done=50)
        self.assertEqual(step.percentage, 50.0)

        # Zero total (edge case)
        step = ProgressStep(total=0, done=10)
        self.assertEqual(step.percentage, 0.0)

        # Over 100% (should be capped)
        step = ProgressStep(total=100, done=150)
        self.assertEqual(step.percentage, 100.0)

        # Exact completion
        step = ProgressStep(total=100, done=100)
        self.assertEqual(step.percentage, 100.0)


class TestOSBuildProgressMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = OSBuildProgressMonitor(verbose=False)
        self.verbose_monitor = OSBuildProgressMonitor(verbose=True)

    def test_init(self):
        """Test OSBuildProgressMonitor initialization."""
        self.assertFalse(self.monitor.verbose)
        self.assertTrue(self.verbose_monitor.verbose)
        self.assertEqual(self.monitor.stages_total, 0)
        self.assertEqual(self.monitor.stages_completed, 0)
        self.assertEqual(self.monitor.current_stage, "")

    def test_parse_json_sequence_line_valid(self):
        """Test parsing valid JSON sequence lines."""
        valid_json = '{"progress": {"name": "test", "total": 10, "done": 5}}'
        result = self.monitor.parse_json_sequence_line(valid_json)

        self.assertIsNotNone(result)
        self.assertEqual(result["progress"]["name"], "test")
        self.assertEqual(result["progress"]["total"], 10)
        self.assertEqual(result["progress"]["done"], 5)

    def test_parse_json_sequence_line_invalid(self):
        """Test parsing invalid JSON sequence lines."""
        invalid_json = "not json"
        result = self.monitor.parse_json_sequence_line(invalid_json)
        self.assertIsNone(result)

    def test_parse_json_sequence_line_empty(self):
        """Test parsing empty lines."""
        result = self.monitor.parse_json_sequence_line("")
        self.assertIsNone(result)

        result = self.monitor.parse_json_sequence_line("   ")
        self.assertIsNone(result)

    def test_extract_progress_info_nested(self):
        """Test extracting nested progress information."""
        monitor = OSBuildProgressMonitor(verbose=False)
        data = {
            "progress": {
                "name": "pipelines/sources",
                "total": 9,
                "done": 2,
                "progress": {"name": "pipeline: build", "total": 7, "done": 3},
            },
            "context": {"pipeline": "build"},
            "message": "Building packages",
        }

        result = monitor.extract_progress_info(data)

        self.assertIsInstance(result, NestedProgressInfo)
        self.assertIsInstance(result.parent, ProgressStep)
        self.assertIsInstance(result.current, ProgressStep)

        self.assertEqual(result.parent.name, "pipelines/sources")
        self.assertEqual(result.parent.total, 9)
        self.assertEqual(result.parent.done, 2)
        self.assertEqual(result.current.name, "pipeline: build")
        self.assertEqual(result.current.total, 7)
        self.assertEqual(result.current.done, 3)
        self.assertEqual(result.context["pipeline"], "build")

    def test_extract_progress_info_simple_returns_none(self):
        """Test that simple progress (without nesting) returns None."""
        data = {"progress": {"name": "pipeline: sources", "total": 5, "done": 3}}

        result = self.monitor.extract_progress_info(data)
        self.assertIsNone(result)

    def test_extract_progress_info_stage_event(self):
        """Test extracting stage event information."""
        data = {
            "stage": {"name": "org.osbuild.rpm"},
            "context": {"stage": "rpm", "pipeline": "build"},
        }

        result = self.monitor.extract_progress_info(data)

        self.assertIsInstance(result, StageEventInfo)
        self.assertEqual(result.stage_name, "org.osbuild.rpm")
        self.assertTrue(result.stage_event)
        self.assertEqual(result.context["stage"], "rpm")

    def test_extract_progress_info_no_progress(self):
        """Test extracting from data with no progress information."""
        data = {"some": "other", "data": "here"}
        result = self.monitor.extract_progress_info(data)
        self.assertIsNone(result)

    def test_extract_progress_info_verbose_message(self):
        """Test verbose message output."""
        data = {"message": "Test message"}

        with patch.object(self.verbose_monitor.console, "print") as mock_print:
            self.verbose_monitor.extract_progress_info(data)
            mock_print.assert_called_once_with("[dim]Test message[/dim]")

        # Non-verbose should not print
        with patch.object(self.monitor.console, "print") as mock_print:
            self.monitor.extract_progress_info(data)
            mock_print.assert_not_called()

    def test_update_progress_nested(self):
        """Test updating progress with nested progress info."""
        mock_progress = Mock()
        task_id = 0

        parent_step = ProgressStep(name="pipelines/sources", total=10, done=3)
        current_step = ProgressStep(name="org.osbuild.rpm", total=50, done=25)
        nested_info = NestedProgressInfo(parent=parent_step, current=current_step)

        self.monitor.update_progress(nested_info, mock_progress, task_id)

        # Should update total and progress
        self.assertEqual(self.monitor.stages_total, 10)
        mock_progress.update.assert_called()

    def test_update_progress_stage_event(self):
        """Test updating progress with stage event info."""
        # Create a fresh monitor to avoid any state issues
        monitor = OSBuildProgressMonitor(verbose=False)
        mock_progress = Mock()
        task_id = 0

        stage_info = StageEventInfo(stage_name="org.osbuild.rpm", stage_event=True)

        monitor.update_progress(stage_info, mock_progress, task_id)

        # Should only update description for stage events
        mock_progress.update.assert_called_once_with(
            task_id, description=stage_info.description
        )

    def test_update_progress_no_progress_object(self):
        """Test update_progress with None progress object."""
        parent_step = ProgressStep(total=10)
        nested_info = NestedProgressInfo(parent=parent_step)

        # Should not raise exception
        self.monitor.update_progress(nested_info, None, 0)
        self.monitor.update_progress(nested_info, Mock(), None)

    def test_monitor_subprocess_output(self):
        """Test monitoring subprocess output."""
        mock_process = Mock()
        mock_progress = Mock()
        task_id = 0

        # Mock stdout with JSON sequence data
        json_lines = [
            b'{"progress": {"name": "pipelines/sources", "total": 3, "done": 0, "progress": {"name": "org.osbuild.rpm", "total": 10, "done": 5}}}\n',
            b"Non-JSON line\n",
            b'{"stage": {"name": "org.osbuild.files"}}\n',
            b"",  # End of output
        ]

        mock_process.stdout.readline.side_effect = json_lines

        with patch.object(self.monitor.console, "print") as mock_console_print:
            self.monitor.monitor_subprocess_output(mock_process, mock_progress, task_id)

            # Should print the non-JSON line
            mock_console_print.assert_called_with("Non-JSON line")

    def test_monitor_subprocess_output_io_error(self):
        """Test monitoring subprocess output with IO error."""
        mock_process = Mock()
        mock_progress = Mock()
        task_id = 0

        mock_process.stdout.readline.side_effect = IOError("Test error")

        with patch.object(self.monitor.console, "print") as mock_console_print:
            self.monitor.monitor_subprocess_output(mock_process, mock_progress, task_id)
            mock_console_print.assert_called_with(
                "[red]Error monitoring output: Test error[/red]"
            )

    def test_run_success(self):
        """Test successful command execution with progress monitoring."""
        mock_process = Mock()
        mock_process.wait.return_value = 0
        mock_process.stdout = None

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.__enter__.return_value = mock_process
            result = self.monitor.run(["echo", "test"])

        self.assertEqual(result, 0)
        mock_popen.assert_called_once()

    def test_run_failure(self):
        """Test failed command execution with progress monitoring."""
        mock_process = Mock()
        mock_process.wait.return_value = 1
        mock_process.stdout = None

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.__enter__.return_value = mock_process
            result = self.monitor.run(["false"])

        self.assertEqual(result, 1)

    def test_run_exception(self):
        """Test command execution with exception."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = OSError("Test error")
            result = self.monitor.run(["invalid-command"])

        self.assertEqual(result, 1)

    def test_run_with_fallback_progress(self):
        """Test command execution with fallback progress bar."""
        # Test that monitor can be created regardless of rich availability
        monitor = OSBuildProgressMonitor(verbose=False)
        self.assertIsNotNone(monitor.console)

        # Test that _progress_args returns a ProgressArgs object
        progress_args = monitor._progress_args()
        self.assertIsInstance(progress_args, ProgressArgs)
        self.assertIsInstance(progress_args.columns, list)
        self.assertIsInstance(progress_args.kwargs, dict)


class TestProgressArgs(unittest.TestCase):
    def test_progress_args_creation(self):
        """Test ProgressArgs dataclass creation."""
        # Test with default values
        args = ProgressArgs()
        self.assertEqual(args.columns, [])
        self.assertEqual(args.kwargs, {})

        # Test with custom values
        columns = ["col1", "col2"]
        kwargs = {"key": "value"}
        args = ProgressArgs(columns=columns, kwargs=kwargs)
        self.assertEqual(args.columns, columns)
        self.assertEqual(args.kwargs, kwargs)

    def test_progress_args_from_monitor(self):
        """Test that OSBuildProgressMonitor._progress_args returns ProgressArgs."""
        monitor = OSBuildProgressMonitor(verbose=False)
        progress_args = monitor._progress_args()

        self.assertIsInstance(progress_args, ProgressArgs)
        self.assertIn("console", progress_args.kwargs)
        self.assertIn("refresh_per_second", progress_args.kwargs)

        # Test that kwargs contain expected values
        self.assertEqual(progress_args.kwargs["refresh_per_second"], 10)
        self.assertEqual(progress_args.kwargs["console"], monitor.console)


class TestNestedProgressInfo(unittest.TestCase):
    def setUp(self):
        parent_step = ProgressStep(
            name="pipelines/sources",
            total=10,
            done=3,
        )
        current_step = ProgressStep(
            name="org.osbuild.rpm",
            total=50,
            done=25,
        )
        self.progress_info = NestedProgressInfo(
            parent=parent_step, current=current_step
        )

    def test_total_property(self):
        """Test that total returns parent.total."""
        self.assertEqual(self.progress_info.total, 10)

    def test_description_property(self):
        """Test description formatting."""
        description = self.progress_info.description
        self.assertIn("Sources Pipelines", description)
        self.assertIn("Rpm", description)
        self.assertIn("25/50", description)

    def test_partial_progress_property(self):
        """Test partial progress calculation."""
        # parent.done (3) + (current.done / current.total) = 3 + (25/50) = 3.5
        expected = 3 + (25 / 50)
        self.assertEqual(self.progress_info.partial_progress, expected)

    def test_completed_property(self):
        """Test completed progress calculation."""
        # Should be min(partial_progress, parent.total)
        partial = 3 + (25 / 50)  # 3.5
        expected = min(partial, 10)  # 3.5
        self.assertEqual(self.progress_info.completed, expected)

    def test_completed_capped_at_total(self):
        """Test that completed is capped at parent.total."""
        # Create scenario where partial would exceed total
        parent_step = ProgressStep(total=2, done=2)
        current_step = ProgressStep(total=10, done=5)
        progress_info = NestedProgressInfo(parent=parent_step, current=current_step)

        # partial would be 2 + 0.5 = 2.5, but should be capped at 2
        self.assertEqual(progress_info.completed, 2.0)

    def test_formatted_name(self):
        """Test name formatting functionality."""
        progress_info = NestedProgressInfo()

        # Test osbuild stage formatting
        self.assertEqual(progress_info.formatted_name("org.osbuild.rpm"), "Rpm")
        self.assertEqual(
            progress_info.formatted_name("org.osbuild.file_system"), "File System"
        )

        # Test pipeline formatting
        self.assertEqual(
            progress_info.formatted_name("pipeline: build"), "Build Pipeline"
        )
        self.assertEqual(
            progress_info.formatted_name("pipelines/sources"), "Sources Pipelines"
        )

        # Test generic formatting
        self.assertEqual(
            progress_info.formatted_name("test-name_here"), "Test Name Here"
        )

    def test_default_creation(self):
        """Test creating NestedProgressInfo with default values."""
        info = NestedProgressInfo()
        self.assertIsInstance(info.parent, ProgressStep)
        self.assertIsInstance(info.current, ProgressStep)
        self.assertEqual(info.current.name, "Unknown")
        self.assertEqual(info.parent.name, "")


class TestStageEventInfo(unittest.TestCase):
    def setUp(self):
        self.stage_info = StageEventInfo(stage_name="org.osbuild.rpm", stage_event=True)

    def test_description_property(self):
        """Test description formatting for stage events."""
        description = self.stage_info.description
        self.assertEqual(description, "Rpm")

    def test_completed_property_raises(self):
        """Test that completed property raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            _ = self.stage_info.completed

    def test_formatted_name(self):
        """Test stage name formatting."""
        stage_info = StageEventInfo(stage_name="org.osbuild.files")
        self.assertEqual(stage_info.description, "Files")


if __name__ == "__main__":
    unittest.main()
