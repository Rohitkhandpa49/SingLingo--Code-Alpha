import re
import unicodedata


_SPACE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?।])")
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def normalize_transcript(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = _SPACE.sub(" ", normalized).strip()
    return _SPACE_BEFORE_PUNCTUATION.sub(r"\1", normalized)


def merge_overlapping_transcripts(previous: str, following: str) -> str:
    left = _TOKEN.findall(normalize_transcript(previous))
    right = _TOKEN.findall(normalize_transcript(following))
    if not left:
        return normalize_transcript(following)
    if not right:
        return normalize_transcript(previous)

    left_folded = [token.casefold() for token in left]
    right_folded = [token.casefold() for token in right]
    overlap = min(len(left), len(right), 24)
    overlap_size = max(
        (
            size
            for size in range(1, overlap + 1)
            if left_folded[-size:] == right_folded[:size]
        ),
        default=0,
    )
    merged_tokens = left + right[overlap_size:]
    merged = " ".join(merged_tokens)
    return _SPACE_BEFORE_PUNCTUATION.sub(r"\1", merged)
