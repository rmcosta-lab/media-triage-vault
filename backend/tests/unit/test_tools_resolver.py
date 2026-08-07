import pytest

from backend.app.core import tools


def test_detect_platform_key_on_windows() -> None:
    assert tools.detect_platform_key() == "windows-x64"


def test_resolve_exiftool_returns_vendored_path() -> None:
    path = tools.resolve_tool("exiftool")
    assert path.is_file()
    assert path.parts[-3:-1] == ("exiftool", "windows-x64")


def test_resolve_ffmpeg_and_ffprobe_return_existing_paths() -> None:
    for name in ("ffmpeg", "ffprobe"):
        path = tools.resolve_tool(name)
        assert path.is_file()


def test_resolve_vendored_tool_raises_on_empty_platform_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.core.tools.sys.platform", "darwin")
    monkeypatch.setattr("backend.app.core.tools.platform.machine", lambda: "arm64")
    with pytest.raises(tools.ToolNotAvailableError):
        tools.resolve_tool("exiftool")


def test_resolve_system_tool_raises_when_missing_from_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.core.tools.shutil.which", lambda name: None)
    with pytest.raises(tools.ToolNotAvailableError):
        tools.resolve_tool("ffmpeg")


def test_detect_platform_key_raises_for_unsupported_combination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.app.core.tools.sys.platform", "linux")
    monkeypatch.setattr("backend.app.core.tools.platform.machine", lambda: "x86_64")
    with pytest.raises(tools.UnsupportedPlatformError):
        tools.detect_platform_key()
