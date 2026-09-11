import re
from collections import Counter


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def extract_text_insights(text: str, max_keywords: int) -> dict[str, object]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())
    keywords = [
        word.strip("'-")
        for word in words
        if len(word.strip("'-")) > 2 and word.strip("'-") not in STOP_WORDS
    ]
    sentence_count = len([part for part in re.split(r"[.!?]+", text) if part.strip()])

    return {
        "word_count": len(words),
        "sentence_count": sentence_count,
        "keywords": [
            {"term": term, "count": count}
            for term, count in Counter(keywords).most_common(max_keywords)
        ],
    }
