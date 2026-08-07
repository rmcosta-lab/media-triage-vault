"""Fixed extension tables — README §6.1-6.3, roadmap Phase 5.

Deliberately not ``stdlib mimetypes``: it layers the Windows registry on top
of its built-in table, which is neither deterministic across machines nor
aware of several extensions this project supports (``.heic``, ``.dng``,
``.cr3``, ``.raf``, ...). A fixed table keeps detection offline and
reproducible (``specs/mission.md`` #1, #6).
"""

from __future__ import annotations

from typing import Literal

MediaCategory = Literal["image", "video"]

# README §6.1 "Imagens padrão" + §6.2 "Imagens RAW" -> "image"
_IMAGE_EXTENSIONS: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".png": "image/png",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".dng": "image/x-adobe-dng",
    ".cr2": "image/x-canon-cr2",
    ".cr3": "image/x-canon-cr3",
    ".nef": "image/x-nikon-nef",
    ".arw": "image/x-sony-arw",
    ".raf": "image/x-fujifilm-raf",
    ".rw2": "image/x-panasonic-rw2",
    ".orf": "image/x-olympus-orf",
}

# README §6.3 "Vídeos" -> "video"
_VIDEO_EXTENSIONS: dict[str, str] = {
    ".mov": "video/quicktime",
    ".mp4": "video/mp4",
    ".m4v": "video/x-m4v",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".3gp": "video/3gpp",
    ".webm": "video/webm",
}

EXTENSION_MIME: dict[str, str] = {**_IMAGE_EXTENSIONS, **_VIDEO_EXTENSIONS}

_IMAGE_CATEGORY: dict[str, MediaCategory] = {extension: "image" for extension in _IMAGE_EXTENSIONS}
_VIDEO_CATEGORY: dict[str, MediaCategory] = {extension: "video" for extension in _VIDEO_EXTENSIONS}

EXTENSION_CATEGORY: dict[str, MediaCategory] = {**_IMAGE_CATEGORY, **_VIDEO_CATEGORY}
