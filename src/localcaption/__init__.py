"""localcaption — fully-local YouTube → transcript pipeline.

A thin orchestrator over yt-dlp, ffmpeg, a speechbrain language identifier,
and three NVIDIA/Qwen ASR checkpoints. All network traffic goes through a
SOCKS5 proxy; no API keys, nothing leaves your machine.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("localcaption")
except PackageNotFoundError:  # editable install before metadata is generated
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
