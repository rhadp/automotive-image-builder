import json
import importlib.util
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, IO

try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        BarColumn,
        TextColumn,
        TimeRemainingColumn,
        SpinnerColumn,
    )
except (ModuleNotFoundError, ImportError):
    import re

    class Task:
        """Represents a progress task."""

        def __init__(self, task_id: int, description: str, total: int = 100):
            self.id = task_id
            self.description = description
            self.total = total
            self.completed = 0.0
            self.started = time.time()

        @property
        def percentage(self) -> float:
            """Calculate completion percentage."""
            if self.total == 0:
                return 0.0
            return min(100.0, (self.completed / self.total) * 100.0)

        @property
        def remaining_time(self) -> str:
            """Estimate remaining time."""
            if self.completed <= 0:
                return "??:??"

            elapsed = time.time() - self.started
            if elapsed <= 0:
                return "??:??"

            rate = self.completed / elapsed
            if rate <= 0:
                return "??:??"

            remaining = (self.total - self.completed) / rate
            minutes, seconds = divmod(int(remaining), 60)
            return f"{minutes:02d}:{seconds:02d}"

    class Progress:
        """Simple progress bar fallback."""

        BAR_WIDTH = 30

        def __init__(self, *_columns, console=None, refresh_per_second=10):
            self.tasks = {}
            self.task_counter = 0
            self.refresh_per_second = refresh_per_second
            self.last_refresh = 0
            self.in_context = False
            if console is not None:
                console.progress = self

        def __enter__(self):
            self.in_context = True
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.in_context = False
            # Print final newline to clean up
            sys.stdout.write("\n")
            sys.stdout.flush()

        def add_task(self, description: str, total: int = 100) -> int:
            """Add a new progress task."""
            task_id = self.task_counter
            self.tasks[task_id] = Task(task_id, description, total)
            self.task_counter += 1
            self._maybe_refresh()
            return task_id

        def update(
            self,
            task_id: int,
            completed: Optional[float] = None,
            description: Optional[str] = None,
            total: Optional[int] = None,
        ):
            """Update a progress task."""
            try:
                task = self.tasks[task_id]
            except KeyError:
                return

            if completed is not None:
                task.completed = completed
            if description is not None:
                task.description = description
            if total is not None:
                task.total = total

            self._maybe_refresh()

        def _maybe_refresh(self):
            """Refresh display if enough time has passed."""
            now = time.time()
            if now - self.last_refresh >= (1.0 / self.refresh_per_second):
                self._refresh()
                self.last_refresh = now

        def _refresh(self):
            """Refresh the progress display."""
            if not self.in_context or not self.tasks:
                return

            task = next(iter(self.tasks.values()))
            completed_width = int((task.percentage / 100.0) * self.BAR_WIDTH)
            progress_bar = "█" * completed_width + "░" * (
                self.BAR_WIDTH - completed_width
            )

            clean_desc = re.sub(r"\[[^\]]*\]", "", task.description)
            desc = clean_desc[:40] + "..." if len(clean_desc) > 40 else clean_desc
            progress_line = (
                f"\r {desc} │{progress_bar}│ "
                f"{task.percentage:5.1f}% ETA {task.remaining_time}"
            )

            # Clear the line and write the new progress line
            sys.stdout.write(f"\r{' ' * 100}\r{progress_line}")
            sys.stdout.flush()

        def refresh(self):
            """Refresh method to mimic rich class."""
            self._maybe_refresh()

    class Console:
        """Simple console fallback for when rich is not available."""

        def __init__(self):
            self._progress = None

        @property
        def progress(self):
            return self._progress

        @progress.setter
        def progress(self, progress: Progress):
            self._progress = progress

        def print(self, text: str, **_kwargs):
            """Print text to stdout, stripping rich markup."""
            text = re.sub(r"\[[^\]]*\]", "", text)
            if self.progress is not None and self.progress.in_context:
                # Clear the current progress line completely
                sys.stdout.write(f"\r{' ' * 100}\r")
                sys.stdout.flush()
                print(text)
                # Redraw the progress bar after printing the text
                self.progress._refresh()
                return
            # No progress bar active, just print the message
            print(text)


@dataclass
class ProgressArgs:
    """Progress arguments for rich Progress constructor."""

    columns: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgressInfo:
    """Base progress information."""

    context: Optional[Dict[str, Any]] = None

    def formatted_name(self, name: str) -> str:
        """Format the name of the progress."""
        if name.startswith("org.osbuild."):
            return name.replace("org.osbuild.", "").replace("_", " ").title()

        if name.startswith("pipeline:"):
            pipeline_name = name.replace("pipeline:", "").strip()
            return f"{pipeline_name.title()} Pipeline"

        if name.startswith("pipelines/"):
            pipeline_name = name.replace("pipelines/", "").strip()
            return f"{pipeline_name.title()} Pipelines"

        return name.replace("_", " ").replace("-", " ").title()

    @property
    def description(self) -> str:
        """Generate a description of the progress."""
        raise NotImplementedError("Subclasses must implement this method")

    @property
    def completed(self) -> float:
        """Calculate the completed percentage of the progress."""
        raise NotImplementedError("Subclasses must implement this method")

    @property
    def total(self) -> int:
        """Get the total number of items to be processed."""
        return 0


@dataclass
class ProgressStep:
    """Represents a single progress step with name, total, and completion."""

    name: str = ""
    total: int = 0
    done: int = 0

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return min(100.0, (self.done / self.total) * 100.0)


@dataclass
class NestedProgressInfo(ProgressInfo):
    """Nested progress information with parent and current steps."""

    parent: ProgressStep = field(default_factory=ProgressStep)
    current: ProgressStep = field(default_factory=lambda: ProgressStep(name="Unknown"))

    @property
    def total(self) -> int:
        """Get the total number of items to be processed."""
        return self.parent.total

    @property
    def description(self) -> str:
        """Generate a description of the parent stage."""
        description = f"{self.formatted_name(self.parent.name)}: {self.formatted_name(self.current.name)}"
        if self.current.total > 0:
            description += f" • {self.current.done}/{self.current.total}"
        return description

    @property
    def partial_progress(self) -> float:
        """Calculate the partial progress of the parent stage."""
        if self.parent.total > 0:
            return self.parent.done + (self.current.done / self.current.total)
        return self.parent.done

    @property
    def completed(self) -> float:
        """Calculate the completed percentage of the parent stage."""
        return min(self.partial_progress, self.parent.total)


@dataclass
class StageEventInfo(ProgressInfo):
    """Stage event information."""

    stage_name: str = "Stage"
    stage_event: bool = False

    @property
    def description(self) -> str:
        """Generate a description of the progress."""
        return f"{self.formatted_name(self.stage_name)}"

    @property
    def completed(self) -> float:
        """Calculate the completed percentage of the progress."""
        raise NotImplementedError("This is a stage event, not a progress")


class OSBuildProgressMonitor:
    """Monitor osbuild JSONSeqMonitor output and display progress using rich."""

    def __init__(self, log_file: str, verbose=False):
        self.console = Console()
        self.stages_total = 0
        self.stages_completed = 0
        self.current_stage = ""
        self.verbose = verbose
        self.log_file = log_file

    def parse_json_sequence_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single JSON sequence line from osbuild monitor output."""
        line = line.strip()
        if not line:
            return None

        try:
            return json.loads(line)
        except json.JSONDecodeError:
            # Not a JSON line, might be other output
            return None

    def _log_result_info(self, data: Dict[str, Any], log_file: IO):
        """Log result information to the log file."""
        result_data = data.get("result", {})
        stage_info = data.get("context", {}).get("pipeline", {}).get("stage", {})
        stage_name = stage_info.get("name", result_data.get("name", ""))
        stage_id = stage_info.get("id", result_data.get("id", ""))

        if stage_name:
            header = f"{stage_name}: {stage_id}" if stage_id else stage_name
            log_file.write(header)

        options = data.get("options")
        if options:
            log_file.write(" ")
            json.dump(options, log_file, indent=2)
        log_file.write("\n")

        duration = data.get("duration")
        if duration is not None:
            log_file.write(f"\n⏱  Duration: {duration:.2f}s\n")
        log_file.flush()

    def extract_progress_info(
        self, data: Dict[str, Any], log_file: Optional[IO] = None
    ) -> Optional[ProgressInfo]:
        """Extract progress information from osbuild JSONSeqMonitor format."""
        message = data.get("message", "").rstrip()
        if message:
            if log_file:
                log_file.write(f"{message}\n")
                log_file.flush()
            if self.verbose:
                self.console.print(f"[dim]{message}[/dim]")

        # Check for result data (stage/module completion)
        if "result" in data and log_file:
            self._log_result_info(data, log_file)

        # Check for osbuild JSONSeqMonitor progress format
        if "progress" in data:
            progress_data = data["progress"]
            if not isinstance(progress_data, dict):
                return None

            # Handle nested progress (current pipeline/stage info)
            nested_progress = progress_data.get("progress", {})
            if isinstance(nested_progress, dict) and nested_progress:
                return NestedProgressInfo(
                    parent=ProgressStep(
                        name=progress_data.get("name", ""),
                        total=progress_data.get("total", 0),
                        done=progress_data.get("done", 0),
                    ),
                    current=ProgressStep(
                        name=nested_progress.get("name", ""),
                        total=nested_progress.get("total", 0),
                        done=nested_progress.get("done", 0),
                    ),
                    context=data.get("context"),
                )
            # Simple progress without nesting
            return None

        # Check for other osbuild events like stage completion
        if "stage" in data:
            stage_data = data.get("stage", {})
            if isinstance(stage_data, dict):
                stage_name = stage_data.get("name", "Unknown")
                # This could be a stage completion event
                return StageEventInfo(
                    stage_name=stage_name,
                    stage_event=True,
                    context=data.get("context"),
                )

        # No recognized progress format
        return None

    def update_progress(self, progress_info: ProgressInfo, progress=None, task_id=None):
        """Update progress display based on progress information."""
        if not progress or task_id is None:
            return

        if isinstance(progress_info, StageEventInfo):
            progress.update(task_id, description=progress_info.description)
        elif progress_info.total > 0:
            if self.stages_total != progress_info.total:
                self.stages_total = progress_info.total
                progress.update(task_id, total=progress_info.total)

            progress.update(
                task_id,
                completed=progress_info.completed,
                description=progress_info.description,
            )

        progress.refresh()

    def monitor_subprocess_output(
        self,
        process: subprocess.Popen,
        progress=None,
        task_id=None,
        log_file: Optional[IO] = None,
    ):
        """Monitor subprocess output line by line and extract progress information."""
        try:
            if process.stdout:
                for line in iter(process.stdout.readline, b""):
                    if not line:
                        break

                    line_str = line.decode("utf-8", errors="ignore").strip()

                    # Try to parse as JSON sequence
                    json_data = self.parse_json_sequence_line(line_str)
                    if json_data:
                        progress_info = self.extract_progress_info(json_data, log_file)
                        if progress_info:
                            self.update_progress(progress_info, progress, task_id)
                    else:
                        # Non-JSON output, only print if it looks important (not empty lines, etc.)
                        if line_str and not line_str.isspace():
                            self.console.print(line_str)
                            if log_file:
                                log_file.write(f"{line_str}\n")
                                log_file.flush()
        except (IOError, OSError) as e:
            self.console.print(f"[red]Error monitoring output: {e}[/red]")

    def _progress_args(self) -> ProgressArgs:
        if importlib.util.find_spec("rich") is not None:
            progress_columns = [
                SpinnerColumn(
                    finished_text="[green][[/green][yellow]🗸[/yellow][green]][/green]"
                ),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
            ]
            progress_kwargs = {
                "console": self.console,
                "auto_refresh": False,
            }
            return ProgressArgs(columns=progress_columns, kwargs=progress_kwargs)

        return ProgressArgs(
            kwargs={
                "console": self.console,
                "refresh_per_second": 10,
            }
        )

    def run(self, cmdline: list, **subprocess_kwargs) -> int:
        """Run a command and monitor its progress."""
        progress_args = self._progress_args()
        with Progress(*progress_args.columns, **progress_args.kwargs) as progress:

            # Start with unknown total - will be updated when pipeline info is received
            task_id = progress.add_task("Preparing build...", total=100)

            try:
                with open(self.log_file, "w", encoding="utf-8") as log_file:
                    with subprocess.Popen(
                        cmdline,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=False,
                        **subprocess_kwargs,
                    ) as process:
                        self.monitor_subprocess_output(
                            process, progress, task_id, log_file
                        )
                        return_code = process.wait()

                    if return_code == 0:
                        # Ensure we show 100% completion
                        progress.update(
                            task_id,
                            completed=(
                                self.stages_total if self.stages_total > 0 else 100
                            ),
                            description="[green]Build completed successfully![/green]",
                        )
                    else:
                        progress.update(
                            task_id,
                            description="[red][✗] Build failed![/red]",
                        )

                    return return_code

            except (subprocess.CalledProcessError, OSError) as e:
                progress.update(
                    task_id,
                    description=f"[red][✗] Error: {e}[/red]",
                )
                return 1
