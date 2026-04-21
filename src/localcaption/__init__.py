"""localcaption — fully-local YouTube → transcript pipeline.

A thin orchestrator over yt-dlp, ffmpeg, and whisper.cpp. No API keys,
nothing leaves your machine.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("localcaption")
except PackageNotFoundError:  # editable install before metadata is generated
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
