"""
Search and reading of notes and manuals saved under data/documents/.

Reads .txt, .md and .json files, splits them into fragments and scores them with
BM25 (pure Python, no embeddings or external libraries). The index is
rebuilt only when a file changes.
"""

import json
import math
import re
import threading
from pathlib import Path

from brain.base.module import ModuleBase
from brain.core.config import Config
from brain.i18n import t
from brain.modules.inventory import normalize

EXTENSIONS = (".txt", ".md", ".json")
MAX_BYTES = 5 * 1024 * 1024
CHUNK_SIZE = 800  # approximate characters per fragment
OVERLAP = 120

K1 = 1.5
B = 0.75

# Common short words skipped when indexing, in both languages the user may write in.
EMPTY = {
    "de", "del", "la", "las", "el", "los", "y", "o", "a", "en", "un", "una", "unos", "unas", "que", "se", "es",
    "por", "con", "para", "al", "lo", "su", "sus", "como", "mas", "pero", "si", "no", "me", "mi", "te", "tu",
    "the", "and", "of", "to", "in", "is", "for", "on",
}


class DocumentError(ValueError):
    """Error with a message the user can understand."""


def tokenize(text):
    """Lowercase keywords, with no accents, articles or an approximate stem."""

    tokens = []

    for word in re.findall(r"[a-z0-9ñ]+", normalize(text)):
        if word in EMPTY or len(word) < 2:
            continue

        if len(word) > 4 and word.endswith("es"):
            word = word[:-2]
        elif len(word) > 3 and word.endswith("s"):
            word = word[:-1]

        tokens.append(word)

    return tokens


def _flatten_json(value, prefix=""):
    """Turns a JSON value into searchable 'key: value' lines."""

    lines = []

    if isinstance(value, dict):
        for key, v in value.items():
            lines += _flatten_json(v, f"{prefix}{key}.")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            if isinstance(v, (dict, list)):
                lines += _flatten_json(v, f"{prefix}{i + 1}.")
            else:
                lines.append(f"{prefix.rstrip('.')}: {v}")
    else:
        lines.append(f"{prefix.rstrip('.')}: {value}")

    return lines


def read_text(path):
    """Reads a text file, accepting UTF-8 (with or without BOM) and Windows-1252."""

    data = Path(path).read_bytes()[:MAX_BYTES]

    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode("latin-1")


def document_text(path):
    """Readable text of a document (.json files are flattened)."""

    text = read_text(path)

    if Path(path).suffix.lower() == ".json":
        try:
            return "\n".join(_flatten_json(json.loads(text)))
        except ValueError:
            pass  # Malformed JSON: treated as plain text

    return text


def split(text, size=CHUNK_SIZE, overlap=OVERLAP):
    """Splits into ~`size`-character fragments, respecting paragraphs and sentences."""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n(?=#)", text) if p.strip()]

    pieces = []

    for paragraph in paragraphs:
        if len(paragraph) <= size:
            pieces.append(paragraph)
            continue

        phrases = re.split(r"(?<=[.!?])\s+|\n", paragraph)
        current = ""

        for phrase in phrases:
            while len(phrase) > size:  # a huge sentence: cut by force
                if current:
                    pieces.append(current)
                    current = ""
                pieces.append(phrase[:size])
                phrase = phrase[size - overlap :]

            if current and len(current) + len(phrase) + 1 > size:
                pieces.append(current)
                current = current[-overlap:].split(" ", 1)[-1] + " " + phrase if overlap else phrase
            else:
                current = f"{current} {phrase}".strip()

        if current:
            pieces.append(current)

    # Merge short consecutive paragraphs so we don't end up with hundreds of tiny fragments.
    fragments = []

    for piece in pieces:
        if fragments and len(fragments[-1]) + len(piece) + 2 <= size // 2:
            fragments[-1] += "\n\n" + piece
        else:
            fragments.append(piece)

    return fragments


class Documents(ModuleBase):
    name = "documents"

    def __init__(self):
        super().__init__()
        self._cache = None  # (signature, index)
        self._block_state = threading.Lock()

    @property
    def folder(self) -> Path:
        return Path(Config.DATA) / "documents"

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def files(self):
        folder = self.folder

        if not folder.exists():
            return []

        return sorted(
            p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS and not p.name.startswith(".")
        )

    def save_file(self, name, content: bytes) -> dict:
        """Saves a file uploaded from the web. PDFs are converted to text so they can be searched."""

        base = re.sub(r"[^\w .()\-]", "_", Path(str(name or "")).name).strip(" .")

        if not base:
            raise DocumentError(t("The file has no name."))

        if len(content) > 25 * 1024 * 1024:
            raise DocumentError(t("The file is too large (25 MB maximum)."))

        extension = Path(base).suffix.lower()

        if extension == ".pdf":
            from brain.utils.pdf import extract_text

            try:
                text = extract_text(content)
            except ValueError as error:
                raise DocumentError(str(error)) from None

            if len(text) < 20:
                raise DocumentError(t("I could not read text from that PDF (it looks scanned, images only). Try a PDF with text or a .txt file."))

            base = Path(base).stem + ".txt"
            content = (f"Manual: {Path(name).stem}\n\n{text}\n").encode("utf-8")
        elif extension not in EXTENSIONS:
            raise DocumentError(t("Only PDF, .txt, .md or .json files can be uploaded."))

        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / base).write_bytes(content)

        return {"name": base, "size_kb": round(len(content) / 1024, 1)}

    def delete(self, name) -> dict:
        path = self.resolve(name)
        path.unlink()

        return {"name": path.name}

    def items(self):
        """Available documents: name (relative path) and size."""

        return [{"name": p.relative_to(self.folder).as_posix(), "size_kb": round(p.stat().st_size / 1024, 1)} for p in self.files()]

    def resolve(self, name):
        """Finds a document by exact or partial name, without leaving the folder."""

        text = str(name or "").strip().replace("\\", "/")

        if not text:
            raise DocumentError(t("The document name is missing."))

        files = self.files()

        if not files:
            raise DocumentError(t("There are no documents. Save .txt, .md or .json files in {0}.", self.folder))

        relative_paths = {p.relative_to(self.folder).as_posix(): p for p in files}
        key = normalize(text)

        for relative, path in relative_paths.items():
            if normalize(relative) == key:
                return path

        # No extension, or partial name
        exact = [r for r in relative_paths if normalize(Path(r).stem) == key or normalize(Path(r).name) == key]

        if not exact:
            exact = [r for r in relative_paths if key in normalize(r)]

        if len(exact) == 1:
            return relative_paths[exact[0]]

        if len(exact) > 1:
            raise DocumentError(t("'{0}' matches several documents: {1}. Give the full name.", name, ", ".join(exact)))

        raise DocumentError(t("I can't find the document '{0}'. Available: {1}.", name, ", ".join(relative_paths)))

    # ------------------------------------------------------------------
    # BM25 index
    # ------------------------------------------------------------------

    def _signature(self):
        return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in self.files())

    def _index(self):
        signature = self._signature()

        with self._block_state:
            if self._cache and self._cache[0] == signature:
                return self._cache[1]

            fragments = []

            for path in self.files():
                try:
                    text = document_text(path)
                except OSError:
                    continue

                name = path.relative_to(self.folder).as_posix()

                for n, chunk in enumerate(split(text), start=1):
                    # The file name also counts: "washer manual" finds washer_manual.md
                    tokens = tokenize(chunk) + tokenize(Path(name).stem.replace("_", " "))

                    if tokens:
                        fragments.append({"document": name, "fragment": n, "text": chunk, "tokens": tokens})

            docs_frequency = {}

            for f in fragments:
                for term in set(f["tokens"]):
                    docs_frequency[term] = docs_frequency.get(term, 0) + 1

            average = sum(len(f["tokens"]) for f in fragments) / len(fragments) if fragments else 0

            index = {"fragments": fragments, "df": docs_frequency, "average": average}

            self._cache = (signature, index)

            return index

    def search(self, query, limit=5):
        """The `limit` most relevant fragments for the query."""

        terms = tokenize(query)

        if not terms:
            raise DocumentError(t("Type some words to search (not just articles or symbols)."))

        index = self._index()
        fragments = index["fragments"]

        if not fragments:
            return []

        n = len(fragments)
        results = []

        for f in fragments:
            length = len(f["tokens"])
            count = {}

            for t_ in f["tokens"]:
                count[t_] = count.get(t_, 0) + 1

            points = 0.0

            for term in set(terms):
                tf = count.get(term, 0)

                if not tf:
                    continue

                df = index["df"][term]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                points += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / index["average"]))

            if points > 0:
                results.append((points, f))

        results.sort(key=lambda r: r[0], reverse=True)

        return [
            {
                "document": f["document"],
                "fragment": f["fragment"],
                "score": round(p, 3),
                "text": f["text"],
            }
            for p, f in results[: max(1, int(limit))]
        ]

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self, name, since=0, maximum=6000):
        """Text of a document, in pages of `maximum` characters."""

        path = self.resolve(name)

        text = document_text(path)

        since = max(0, int(since or 0))
        maximum = min(max(500, int(maximum or 6000)), 20000)

        chunk = text[since : since + maximum]

        result = {
            "document": path.relative_to(self.folder).as_posix(),
            "since": since,
            "until": since + len(chunk),
            "total_chars": len(text),
            "text": chunk,
        }

        if since + maximum < len(text):
            result["next_from"] = since + maximum

        return result
