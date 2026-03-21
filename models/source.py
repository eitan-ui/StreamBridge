import json
import os
from dataclasses import dataclass, asdict
from typing import List

from models.config import APP_DATA_DIR

SOURCES_FILE = os.path.join(APP_DATA_DIR, "sources.json")


@dataclass
class Source:
    name: str
    url: str
    notes: str = ""


class SourceManager:
    def __init__(self) -> None:
        self._sources: List[Source] = []
        self.load()

    @property
    def sources(self) -> List[Source]:
        return list(self._sources)

    def add(self, source: Source) -> None:
        self._sources.append(source)
        self.save()

    def update(self, index: int, source: Source) -> None:
        if 0 <= index < len(self._sources):
            self._sources[index] = source
            self.save()

    def remove(self, index: int) -> None:
        if 0 <= index < len(self._sources):
            self._sources.pop(index)
            self.save()

    def move(self, from_index: int, to_index: int) -> None:
        if 0 <= from_index < len(self._sources) and 0 <= to_index < len(self._sources):
            item = self._sources.pop(from_index)
            self._sources.insert(to_index, item)
            self.save()

    def get(self, index: int) -> Source | None:
        if 0 <= index < len(self._sources):
            return self._sources[index]
        return None

    def save(self) -> None:
        with open(SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in self._sources], f, indent=2)

    def load(self) -> None:
        if not os.path.exists(SOURCES_FILE):
            self._sources = []
            return
        try:
            with open(SOURCES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._sources = [Source(**item) for item in data]
        except (json.JSONDecodeError, TypeError, KeyError):
            self._sources = []
