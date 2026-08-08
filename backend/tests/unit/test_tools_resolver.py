from pathlib import Path

import pytest

from backend.app.core import tools


def test_detect_platform_key_on_windows() -> None:
    assert tools.detect_platform_key() == "windows-x64"


def test_resolve_exiftool_returns_vendored_path() -> None:
    path = tools.resolve_tool("exiftool")
    assert path.is_file()
    assert path.parts[-3:-1] == ("exiftool", "windows-x64")


def test_resolve_ffmpeg_and_ffprobe_return_discovered_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    discovered: dict[tools.ToolName, Path] = {
        "ffmpeg": tmp_path / "ffmpeg.exe",
        "ffprobe": tmp_path / "ffprobe.exe",
    }
    for path in discovered.values():
        path.touch()
    monkeypatch.setattr(
        "backend.app.core.tools.shutil.which",
        lambda name: str(discovered[name]),
    )

    for name, expected in discovered.items():
        assert tools.resolve_tool(name) == expected


def test_resolve_vendored_tool_raises_on_empty_platform_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.core.tools.sys.platform", "darwin")
    monkeypatch.setattr("backend.app.core.tools.platform.machine", lambda: "arm64")
    with pytest.raises(tools.ToolNotAvailableError):
        tools.resolve_tool("exiftool")


@pytest.mark.parametrize("name", ["ffmpeg", "ffprobe"])
def test_resolve_system_tool_raises_when_missing_from_path(
    name: tools.ToolName,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.core.tools.shutil.which", lambda name: None)
    with pytest.raises(tools.ToolNotAvailableError) as exc_info:
        tools.resolve_tool(name)
    assert exc_info.value.tool == name
    assert "restart the application process" in str(exc_info.value)
    assert "vendor it under" not in str(exc_info.value)


def test_detect_platform_key_raises_for_unsupported_combination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.core.tools.sys.platform", "linux")
    monkeypatch.setattr("backend.app.core.tools.platform.machine", lambda: "x86_64")
    with pytest.raises(tools.UnsupportedPlatformError):
        tools.detect_platform_key()


def test_resolve_vendored_tool_normalizes_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.core.tools.sys.platform", "linux")
    monkeypatch.setattr("backend.app.core.tools.platform.machine", lambda: "x86_64")
    with pytest.raises(tools.ToolNotAvailableError) as exc_info:
        tools.resolve_tool("exiftool")
    assert exc_info.value.tool == "exiftool"
    assert "No vendored tool slot" in str(exc_info.value)
