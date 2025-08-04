import json
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    SpinnerColumn,
)


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

    def __init__(self, verbose=False):
        self.console = Console()
        self.stages_total = 0
        self.stages_completed = 0
        self.current_stage = ""
        self.verbose = verbose

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

    def extract_progress_info(self, data: Dict[str, Any]) -> Optional[ProgressInfo]:
        """Extract progress information from osbuild JSONSeqMonitor format."""
        message = data.get("message", "").rstrip()
        if self.verbose and message:
            self.console.print(f"[dim]{message}[/dim]")

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

    def monitor_subprocess_output(
        self, process: subprocess.Popen, progress=None, task_id=None
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
                        progress_info = self.extract_progress_info(json_data)
                        if progress_info:
                            self.update_progress(progress_info, progress, task_id)
                    else:
                        # Non-JSON output, only print if it looks important (not empty lines, etc.)
                        if line_str and not line_str.isspace():
                            self.console.print(line_str)
        except (IOError, OSError) as e:
            self.console.print(f"[red]Error monitoring output: {e}[/red]")

    def run(self, cmdline: list, **subprocess_kwargs) -> int:
        """Run a command and monitor its progress."""
        with Progress(
            SpinnerColumn(
                finished_text="[green][[/green][yellow]🗸[/yellow][green]][/green]"
            ),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console,
            refresh_per_second=10,  # More frequent updates for smoother progress
        ) as progress:

            # Start with unknown total - will be updated when pipeline info is received
            task_id = progress.add_task("Preparing build...", total=100)

            try:
                with subprocess.Popen(
                    cmdline,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=False,
                    **subprocess_kwargs,
                ) as process:
                    self.monitor_subprocess_output(process, progress, task_id)
                    return_code = process.wait()

                if return_code == 0:
                    # Ensure we show 100% completion
                    progress.update(
                        task_id,
                        completed=self.stages_total if self.stages_total > 0 else 100,
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
