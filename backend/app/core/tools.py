"""Resolve external tool executables (ExifTool, FFmpeg, FFprobe).

ExifTool is vendored per-platform under ``tools/exiftool/<platform>/``.
FFmpeg/FFprobe are an interim exception: the official Windows build is too
large to vendor into git history for the MVP, so they are discovered once
from the system PATH instead. See ``specs/tech-stack.md`` "Bundled
binaries" for the full rationale. Every call site must go through
``resolve_tool``/``run_tool`` — never invoke a bare command name directly.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

PlatformKey = Literal["windows-x64", "macos-arm64"]
ToolName = Literal["exiftool", "ffmpeg", "ffprobe"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_VENDORED_TOOLS: frozenset[ToolName] = frozenset({"exiftool"})


class UnsupportedPlatformError(RuntimeError):
    """Raised when the current OS/architecture has no vendored tool slot."""


class ToolNotAvailableError(RuntimeError):
    """Raised when a tool cannot be resolved to an executable path."""

    def __init__(self, tool: ToolName, message: str) -> None:
        self.tool = tool
        super().__init__(message)


def detect_platform_key() -> PlatformKey:
    """Map the running OS/architecture to a ``tools/<name>/<platform>/`` directory name."""
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
        return "windows-x64"
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    raise UnsupportedPlatformError(
        f"No vendored tool slot for platform={sys.platform!r} machine={machine!r}"
    )


def resolve_tool(name: ToolName) -> Path:
    """Resolve ``name`` to an absolute executable path.

    Never falls back to a bare command name — callers pass the resolved
    path to `subprocess` themselves, or use `run_tool` below.
    """
    if name in _VENDORED_TOOLS:
        return _resolve_vendored(name)
    return _resolve_system(name)


def _resolve_vendored(name: ToolName) -> Path:
    try:
        platform_key = detect_platform_key()
    except UnsupportedPlatformError as error:
        raise ToolNotAvailableError(name, str(error)) from error
    suffix = ".exe" if platform_key == "windows-x64" else ""
    path = _REPO_ROOT / "tools" / name / platform_key / f"{name}{suffix}"
    if not path.is_file():
        raise ToolNotAvailableError(
            name, f"{name} is not vendored for {platform_key} (expected at {path})"
        )
    return path


def _resolve_system(name: ToolName) -> Path:
    found = shutil.which(name)
    if found is None:
        raise ToolNotAvailableError(
            name,
            f"{name} was not found on PATH. Install FFmpeg locally "
            "(for example, `winget install Gyan.FFmpeg` on Windows), then "
            "restart the application process (and terminal, if applicable) "
            "so it inherits the updated PATH.",
        )
    return Path(found)


def require_tools(*names: ToolName) -> None:
    """Fail before a pipeline starts if any required local tool is unavailable."""
    for name in names:
        resolve_tool(name)


def run_tool(
    name: ToolName,
    args: list[str],
    *,
    check: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Resolve ``name`` and run it with ``args`` as an argument list (never a shell string)."""
    executable = resolve_tool(name)
    return subprocess.run(
        [str(executable), *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )
