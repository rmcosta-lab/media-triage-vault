"""One-time authoring script for the Phase 2 test fixtures.

Not run by pytest. Run manually (`uv run python
backend/tests/fixtures/generate_fixtures.py`) whenever a fixture needs to
be regenerated; the output files are committed to the repo like any other
test asset.
"""

from __future__ import annotations

from pathlib import Path

import pillow_heif
from PIL import Image

from backend.app.core.tools import run_tool

FIXTURES_DIR = Path(__file__).resolve().parent

TOKYO_LATITUDE = "35.6762"
TOKYO_LONGITUDE = "139.6503"


def _tiny_image(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (32, 32), color=color)


def make_iphone_jpeg_with_gps() -> None:
    path = FIXTURES_DIR / "iphone_jpeg_gps.jpg"
    _tiny_image((90, 130, 200)).save(path, format="JPEG")
    run_tool(
        "exiftool",
        [
            "-overwrite_original",
            "-Make=Apple",
            "-Model=iPhone 14 Pro",
            f"-GPSLatitude={TOKYO_LATITUDE}",
            "-GPSLatitudeRef=N",
            f"-GPSLongitude={TOKYO_LONGITUDE}",
            "-GPSLongitudeRef=E",
            "-DateTimeOriginal=2026:07:30 15:20:00",
            str(path),
        ],
        check=True,
    )


def make_iphone_heic() -> None:
    path = FIXTURES_DIR / "iphone_heic.heic"
    pillow_heif.register_heif_opener()
    _tiny_image((150, 120, 90)).save(path, format="HEIF", quality=50)
    run_tool(
        "exiftool",
        [
            "-overwrite_original",
            "-Make=Apple",
            "-Model=iPhone 14 Pro",
            "-DateTimeOriginal=2026:07:30 15:25:00",
            str(path),
        ],
        check=True,
    )


def make_whatsapp_jpeg() -> None:
    path = FIXTURES_DIR / "IMG-20260730-WA0001.jpg"
    _tiny_image((60, 60, 60)).save(path, format="JPEG")


def make_screenshot_png() -> None:
    path = FIXTURES_DIR / "Screenshot_20260730-152000.png"
    _tiny_image((240, 240, 240)).save(path, format="PNG")


def make_sample_video() -> None:
    path = FIXTURES_DIR / "sample_video.mp4"
    if path.exists():
        path.unlink()
    run_tool(
        "ffmpeg",
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:d=1:r=10",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )


def make_jpeg_no_exif() -> None:
    path = FIXTURES_DIR / "jpeg_no_exif.jpg"
    _tiny_image((10, 200, 10)).save(path, format="JPEG")
    run_tool("exiftool", ["-overwrite_original", "-all=", str(path)], check=True)


def make_misnamed_video_as_jpg() -> None:
    """MP4 content saved under a `.jpg` name — Phase 5's mismatch fixture."""
    source = FIXTURES_DIR / "sample_video.mp4"
    target = FIXTURES_DIR / "misnamed_video_as_jpg.jpg"
    target.write_bytes(source.read_bytes())


def make_corrupt_video() -> None:
    """First 256 bytes of `sample_video.mp4` — Phase 6's VIDEO_UNREADABLE fixture.

    Still starts with a valid `ftyp` box (Phase 5 detects media_kind="video"),
    but is truncated well before any decodable frame, so FFprobe cannot find
    a video stream in it.
    """
    source = FIXTURES_DIR / "sample_video.mp4"
    target = FIXTURES_DIR / "corrupt_video.mp4"
    target.write_bytes(source.read_bytes()[:256])


def main() -> None:
    make_iphone_jpeg_with_gps()
    make_iphone_heic()
    make_whatsapp_jpeg()
    make_screenshot_png()
    make_sample_video()
    make_jpeg_no_exif()
    make_misnamed_video_as_jpg()
    make_corrupt_video()
    print(f"Fixtures written to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
