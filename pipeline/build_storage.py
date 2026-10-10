"""Disposable, replayable build records and bounded JSON hashing."""

import hashlib
import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
import tempfile

from pipeline.controlled_ntvmr import encoded


MAX_EXPANDED_PAIRS = 1_000_000


def check_expansion(witnesses, verses):
    if witnesses * verses > MAX_EXPANDED_PAIRS:
        raise ValueError("Expanded coverage exceeds 1,000,000 witness/verse pairs; "
                         "use build_browser_data() or python build_collection.py for a bounded build")


@contextmanager
def record_store(root):
    cache = Path(root) / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-records-", dir=cache) as directory, ExitStack() as stack:
        def factory(name):
            records = JsonRecords(Path(directory) / (name + ".jsonl"))
            stack.callback(records.close)
            return records
        yield factory


class JsonRecords:
    """Append-only JSON lines; iteration keeps only one record in memory.

    The caller owns the temporary directory. Negative indexing is needed only
    for the latest catalogue metadata while extracting its contents report.
    """

    def __init__(self, path):
        self.path = path
        self.output = path.open("w", encoding="utf-8", newline="\n")
        self.count = 0
        self.recent = []

    def append(self, record):
        self.output.write(encoded(record) + "\n")
        self.count += 1
        self.recent = [*self.recent[-1:], record]

    def extend(self, records):
        for record in records:
            self.append(record)

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if index not in (-1, -2):
            raise IndexError("Build records support only the two latest records")
        return self.recent[index]

    def __iter__(self):
        self.output.flush()
        with self.path.open(encoding="utf-8") as stream:
            for line in stream:
                yield json.loads(line)

    def close(self):
        self.output.close()


def records_digest(records, *, omit=()):
    """Exactly digest(encoded(list(records))), without creating that list/string."""
    result = hashlib.sha256(b"[")
    separator = b""
    for record in records:
        result.update(separator)
        result.update(encoded({k: v for k, v in record.items() if k not in omit}).encode("utf-8"))
        separator = b","
    result.update(b"]")
    return result.hexdigest()
