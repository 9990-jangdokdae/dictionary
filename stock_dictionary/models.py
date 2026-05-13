from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _non_blank(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    return text


def _parse_aliases(value: list[str] | str) -> list[str]:
    if isinstance(value, str):
        parsed = json.loads(value)
    else:
        parsed = value
    if not isinstance(parsed, list):
        raise ValueError("aliases must be a JSON array")
    aliases: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            raise ValueError("aliases must contain strings only")
        text = item.strip()
        if text and text not in aliases:
            aliases.append(text)
    return aliases


def aliases_to_json(aliases: list[str]) -> str:
    return json.dumps(aliases, ensure_ascii=False)


class CsvModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    def to_csv_row(self) -> dict[str, str]:
        row: dict[str, str] = {}
        for name, value in self.model_dump().items():
            if name == "aliases":
                row[name] = aliases_to_json(value)
            else:
                row[name] = "" if value is None else str(value)
        return row


class RawTerm(CsvModel):
    term: str
    raw_definition: str
    source_name: str
    source_url: str
    collected_at: str

    _term_required = field_validator("term", "raw_definition", "source_name", "source_url", "collected_at")(_non_blank)


class CleanedTerm(CsvModel):
    term: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    definition: str
    source_name: str
    source_url: str

    _required = field_validator("term", "category", "definition", "source_name")(_non_blank)

    @field_validator("aliases", mode="before")
    @classmethod
    def validate_aliases(cls, value: Any) -> list[str]:
        return _parse_aliases(value if value is not None else [])


class ReviewRequiredTerm(CsvModel):
    term: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    reason: str
    source_name: str
    source_url: str
    notes: str = ""

    _required = field_validator("term", "category", "reason", "source_name")(_non_blank)

    @field_validator("aliases", mode="before")
    @classmethod
    def validate_aliases(cls, value: Any) -> list[str]:
        return _parse_aliases(value if value is not None else [])


class ScrapeFailure(CsvModel):
    source_name: str
    source_url: str
    failure_stage: str
    error_message: str
    attempted_at: str

    _required = field_validator("source_name", "source_url", "failure_stage", "error_message", "attempted_at")(_non_blank)
