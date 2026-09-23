"""High-level orchestration: URL → transcript artefacts.

Flow:

1. ``yt-dlp`` downloads the best audio (all traffic through the proxy).
2. ``ffmpeg`` re-encodes to 16 kHz mono WAV.
3. Language ID (speechbrain ECAPA-TDNN) picks the ASR model:
   Russian → Qwen3-ASR, English → Parakeet, anything else → Nemotron.
4. The chosen model runs in its own virtualenv and emits timed segments.

This module is the public Python API. The CLI is a thin wrapper around
:func:`transcribe_url`.
"""

from __future__ import annotations

import shutil
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _logging as log
from . import asr, langid, models
from .asr import TranscriptionResult, output_file
from .audio import to_wav
from .chapters import (
    Chapter,
    build_chaptered_markdown,
    chapters_as_dicts,
    chapters_from_info,
    load_segments,
    write_chaptered_md,
    write_chapters_json,
)
from .download import download_audio
from .index import upsert_index
from .languages import code_for_name, name_for_code
from .summary import DEFAULT_MODEL as DEFAULT_SUMMARY_MODEL
from .summary import write_summary


@dataclass(frozen=True)
class PipelineResult:
    """Aggregated result of one URL → transcript run."""

    source_url: str
    audio_path: Path | None
    wav_path: Path | None
    transcripts: TranscriptionResult
    duration_s: float | None = None
    summary: Path | None = None
    chapters_json: Path | None = None
    chaptered_md: Path | None = None

    @property
    def language(self) -> str:
        return self.transcripts.language

    @property
    def model(self) -> str:
        return self.transcripts.model


def _is_local_file(source: str) -> bool:
    if "://" in source:
        return False
    return Path(source).is_file()


def normalize_language(value: str) -> str:
    """Turn ``"auto"``/``"Russian"``/``"ru"`` into a routing code."""
    value = (value or "").strip()
    if value.lower() in {"", "auto", "detect"}:
        return "auto"
    return code_for_name(value)


def resolve_model(language: str, wav: Path, force_model: str | None) -> tuple[str, str]:
    """Decide the ASR model and detected language code.

    Returns ``(model_key, language_code)``. With ``language="auto"`` the
    language-ID model votes; a low-confidence result falls back to the
    multilingual model.
    """
    if force_model is not None:
        spec = models.get_model(force_model)
        code = normalize_language(language)
        if code == "auto":
            code = {
                models.ROLE_RU: "ru",
                models.ROLE_EN: "en",
                models.ROLE_MULTI: "und",
            }.get(spec.role, "und")
        return force_model, code

    code = normalize_language(language)
    if code == "auto":
        result = langid.detect_language(wav)
        if result.confident:
            log.info(
                f"language: {result.name} ({result.code}, p={result.score:.2f})"
            )
            return asr.model_for_language(result.code), result.code
        log.warn(
            f"language unclear (best: {result.name} p={result.score:.2f}) "
            "→ multilingual model"
        )
        return asr.MULTILINGUAL_MODEL, result.code

    return asr.model_for_language(code), code


def transcribe_url(
    url: str,
    *,
    out_dir: Path,
    language: str = "auto",
    force_model: str | None = None,
    keep_intermediate: bool = False,
    stem: str | None = None,
    summary: bool = False,
    summary_model: str = DEFAULT_SUMMARY_MODEL,
    summary_prompt: Path | None = None,
    output_format: str = "md",
    cookies: str | None = None,
    proxy: str | None = None,
    force_rotate: bool = False,
) -> PipelineResult:
    """Run the full pipeline on *url* and return the produced artefacts.

    *url* may be an actual URL or a path to a local video/audio file.

    Parameters
    ----------
    url:
        Any URL ``yt-dlp`` can resolve, or a local file path.
    out_dir:
        Directory for the final transcript files.
    language:
        ``"auto"`` (default) runs language ID; an ISO code or language name
        (``"ru"``/``"Russian"``) skips detection.
    force_model:
        Registry key of the ASR model to use, overriding routing.
    keep_intermediate:
        If True, leave the downloaded audio + 16 kHz WAV in ``out_dir/.work``.
    stem:
        Basename for transcript files. Defaults to the audio/file stem.
    summary:
        If True, POST the ``.txt`` transcript to local Ollama and write
        ``<id>.summary.md``. Failures are warnings; they do not raise.
    """
    if force_model is not None:
        models.get_model(force_model)  # validate early

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    audio_path: Path | None = None
    wav_path: Path | None = None
    duration_s: float | None = None
    chapters_json: Path | None = None
    chaptered_md: Path | None = None
    index_entry: dict[str, Any] | None = None
    try:
        if _is_local_file(url):
            audio_path = Path(url).resolve()
            info: dict[str, Any] = {
                "id": audio_path.stem,
                "title": audio_path.name,
                "webpage_url": str(audio_path),
            }
        else:
            downloaded = download_audio(
                url, work_dir, cookies=cookies, proxy=proxy, force_rotate=force_rotate
            )
            audio_path = downloaded.path
            info = downloaded.info or {}

        wav_path = work_dir / f"{audio_path.stem}.16k.wav"
        to_wav(audio_path, wav_path)
        duration_s = _wav_duration_s(wav_path)

        model_key, code = resolve_model(language, wav_path, force_model)

        out_base = out_dir / (stem or audio_path.stem)
        transcripts = asr.transcribe(
            wav_path,
            out_base,
            language=language,
            model=model_key,
            detected_language=code,
            output_format=output_format,
        )

        chapters = chapters_from_info(info)
        if chapters:
            try:
                if output_format == "md":
                    # Single-file mode: fold the chaptered transcript into the
                    # one .md produced by ASR so exactly one artefact remains.
                    _write_chaptered_into_md(out_base, chapters, transcripts)
                    chapters_json = None
                    chaptered_md = None
                else:
                    chapters_json, chaptered_md = _write_chapter_artefacts(
                        out_base, chapters, transcripts
                    )
            except OSError as exc:
                log.warn(f"could not write chapter files: {exc}")

        index_entry = _index_entry(url, audio_path, info, chapters, transcripts)
    finally:
        if not keep_intermediate:
            shutil.rmtree(work_dir, ignore_errors=True)
            audio_path = None
            wav_path = None

    if index_entry is not None:
        try:
            upsert_index(index_entry)
        except Exception as exc:
            # Index is best-effort: a corrupt jsonl row must not fail a finished run.
            log.warn(f"could not update search index: {exc}")

    summary_path: Path | None = None
    if summary:
        summary_path = write_summary(
            transcripts.txt,
            model=summary_model,
            prompt_path=summary_prompt,
        )

    log.info(f"done ({name_for_code(transcripts.language)}, {transcripts.model})")
    return PipelineResult(
        source_url=url,
        audio_path=audio_path,
        wav_path=wav_path,
        transcripts=transcripts,
        duration_s=duration_s,
        summary=summary_path,
        chapters_json=chapters_json,
        chaptered_md=chaptered_md,
    )


def _wav_duration_s(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wf:
            rate = wf.getframerate()
            if not rate:
                return None
            return wf.getnframes() / float(rate)
    except Exception:
        return None


def _write_chapter_artefacts(
    out_base: Path,
    chapters: list[Chapter],
    transcripts: TranscriptionResult,
) -> tuple[Path, Path]:
    chapters_json = write_chapters_json(output_file(out_base, ".chapters.json"), chapters)
    fallback = ""
    if transcripts.txt.exists():
        fallback = transcripts.txt.read_text(encoding="utf-8", errors="replace")
    chaptered_md = write_chaptered_md(
        output_file(out_base, ".chaptered.md"),
        chapters,
        load_segments(out_base),
        fallback_text=fallback,
    )
    return chapters_json, chaptered_md


def _write_chaptered_into_md(
    out_base: Path,
    chapters: list[Chapter],
    transcripts: TranscriptionResult,
) -> Path | None:
    """Fold chaptered headings into the single ``.md`` produced by ASR.

    Keeps the run's output to exactly one file: the chaptered transcript
    replaces the bare text inside the ``.md``.
    """
    md_path = transcripts.md
    if md_path is None or not md_path.exists():
        return None
    segments = load_segments(out_base)
    fallback = md_path.read_text(encoding="utf-8", errors="replace") if not segments else ""
    chaptered = build_chaptered_markdown(chapters, segments, fallback_text=fallback)
    if not chaptered:
        return None
    md_path.write_text(chaptered, encoding="utf-8")
    return md_path


def _index_entry(
    url: str,
    audio_path: Path,
    info: dict[str, Any],
    chapters: list[Chapter],
    transcripts: TranscriptionResult,
) -> dict[str, Any]:
    video_id = str(info.get("id") or audio_path.stem)
    title = info.get("title") or video_id
    webpage = info.get("webpage_url") or info.get("original_url") or url
    return {
        "id": video_id,
        "url": webpage,
        "title": title,
        "duration": info.get("duration"),
        "language": transcripts.language,
        "model": transcripts.model,
        "chapters": chapters_as_dicts(chapters),
        "transcript": str(transcripts.txt.resolve()),
    }
