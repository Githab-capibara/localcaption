"""Language names: the SpeechBrain language-ID model emits display names
(``"Russian"``, ``"English"``, …) while the ASR routing speaks ISO 639-1
codes. This module bridges the two.
"""

from __future__ import annotations

# All 45 classes of speechbrain/lang-id-commonlanguage_ecapa, mapped to the
# ISO code we use internally. Variants we do not otherwise distinguish keep
# a region-qualified pseudo-code so nothing is silently dropped.
_NAME_TO_CODE: dict[str, str] = {
    "basque": "eu",
    "romansh_sursilvan": "rm",
    "sakha": "sah",
    "georgian": "ka",
    "greek": "el",
    "hakha_chin": "cnh",
    "ukrainian": "uk",
    "interlingua": "ia",
    "persian": "fa",
    "polish": "pl",
    "dutch": "nl",
    "chinese_hongkong": "zh-hk",
    "japanese": "ja",
    "portuguese": "pt",
    "italian": "it",
    "catalan": "ca",
    "chuvash": "cv",
    "swedish": "sv",
    "spanish": "es",
    "slovenian": "sl",
    "tamil": "ta",
    "breton": "br",
    "russian": "ru",
    "czech": "cs",
    "english": "en",
    "french": "fr",
    "tatar": "tt",
    "welsh": "cy",
    "kyrgyz": "ky",
    "esperanto": "eo",
    "kinyarwanda": "rw",
    "dhivehi": "dv",
    "turkish": "tr",
    "latvian": "lv",
    "estonian": "et",
    "arabic": "ar",
    "frisian": "fy",
    "mongolian": "mn",
    "chinese_taiwan": "zh-tw",
    "indonesian": "id",
    "maltese": "mt",
    "kabyle": "kab",
    "romanian": "ro",
    "chinese_china": "zh",
    "german": "de",
}

# Codes the ASR models accept, mapped back to a friendly name for reports.
_CODE_TO_NAME: dict[str, str] = {
    code: name.replace("_", " ").title() for name, code in _NAME_TO_CODE.items()
}
_CODE_TO_NAME.update(
    {
        "und": "Undetermined",
        "ru": "Russian",
        "en": "English",
    }
)


def code_for_name(name: str) -> str:
    """Map a SpeechBrain label (``"Russian"``) to an ISO-ish code (``"ru"``)."""
    key = name.strip().strip("'").lower()
    return _NAME_TO_CODE.get(key, key if len(key) <= 3 else "und")


def name_for_code(code: str) -> str:
    """Human-readable name for an ISO code, falling back to the code itself."""
    return _CODE_TO_NAME.get(code.lower(), code)
