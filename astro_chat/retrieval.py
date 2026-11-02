"""Pure-Python BM25 over chunked .txt books.

Books are OCR text and some of it is garbage, so chunks whose characters are
mostly not letters are dropped. Each chunk keeps the book name and, when the
text shows them, the page (form feed or "Page N") and chapter ("CHAPTER N").
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CHUNK_WORDS = 180
MIN_ALPHA = 0.6
MIN_WORDS = 8
K1, B = 1.5, 0.75

_TOKEN = re.compile(r"[a-z]{2,}")
_PAGE = re.compile(r"^\s*page\s+(\d+)\s*$", re.I)
_CHAPTER = re.compile(r"^\s*(?:chapter|ch\.)\s+([0-9ivxlc]+)\b", re.I)
STOP = frozenset("the of and to in is an be by for if on or with as at it his he "
                 "will this that from are was its which who what not but".split())


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP]


def alpha_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    return sum(c.isalpha() for c in chars) / len(chars) if chars else 0.0


@dataclass
class Chunk:
    book: str
    page: int | None
    chapter: str | None
    text: str


def chunk_book(book: str, text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    page: int | None = 1 if "\f" in text else None
    chapter: str | None = None
    words: list[str] = []
    start = (page, chapter)

    def flush():
        nonlocal words
        body = " ".join(words)
        if len(words) >= MIN_WORDS and alpha_ratio(body) >= MIN_ALPHA:
            chunks.append(Chunk(book, start[0], start[1], body))
        words = []

    for i, part in enumerate(text.split("\f")):
        if i:
            flush()  # a page break starts a new chunk so page tags stay right
            page = (page or 1) + 1
        for line in part.splitlines():
            if m := _PAGE.match(line):
                flush()
                page = int(m.group(1))
                continue
            if m := _CHAPTER.match(line):
                flush()
                chapter = m.group(1).upper()
            if not words:
                start = (page, chapter)
            words.extend(line.split())
            if len(words) >= CHUNK_WORDS:
                flush()
    flush()
    return chunks


class BookIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.tfs = [Counter(tokens(c.text)) for c in chunks]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df: Counter = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @classmethod
    def load(cls, books_dir: str) -> "BookIndex":
        root = Path(books_dir)
        chunks: list[Chunk] = []
        if root.is_dir():
            for path in sorted(root.glob("*.txt")):
                text = path.read_text(encoding="utf-8", errors="replace")
                chunks.extend(chunk_book(path.stem, text))
        return cls(chunks)

    def search(self, query: str, k: int = 5) -> list[Chunk]:
        q = set(tokens(query))
        scored = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (K1 + 1) / (
                        f + K1 * (1 - B + B * self.lens[i] / (self.avg or 1)))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [self.chunks[i] for _, i in scored[:k]]
