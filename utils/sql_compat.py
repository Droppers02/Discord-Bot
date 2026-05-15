from __future__ import annotations

import re
from typing import Any, Iterable, Sequence


_INSERT_OR_IGNORE_RE = re.compile(r"\bINSERT\s+OR\s+IGNORE\b", re.IGNORECASE)
_INSERT_OR_REPLACE_RE = re.compile(r"\bINSERT\s+OR\s+REPLACE\b", re.IGNORECASE)
_DATETIME_NOW_RE = re.compile(r"datetime\(\s*'now'\s*\)", re.IGNORECASE)
_DATETIME_CALL_RE = re.compile(r"datetime\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", re.IGNORECASE)


def _replace_qmark_placeholders(query: str) -> str:
    parts: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0

    while index < len(query):
        char = query[index]

        if char == "'" and not in_double_quote:
            if in_single_quote and index + 1 < len(query) and query[index + 1] == "'":
                parts.append("''")
                index += 2
                continue
            in_single_quote = not in_single_quote
            parts.append(char)
            index += 1
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            parts.append(char)
            index += 1
            continue

        if char == "?" and not in_single_quote and not in_double_quote:
            parts.append("%s")
        else:
            parts.append(char)

        index += 1

    return "".join(parts)


def translate_query(query: str) -> str:
    if _INSERT_OR_REPLACE_RE.search(query):
        raise ValueError(
            "SQLite syntax 'INSERT OR REPLACE' is not supported automatically in PostgreSQL. "
            "Rewrite the query to use INSERT ... ON CONFLICT ... DO UPDATE explicitly."
        )

    translated = _INSERT_OR_IGNORE_RE.sub("INSERT", query)
    if translated != query and "ON CONFLICT" not in translated.upper():
        translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    translated = _DATETIME_NOW_RE.sub("CURRENT_TIMESTAMP", translated)
    translated = _DATETIME_CALL_RE.sub(r"CAST(\1 AS timestamp)", translated)
    translated = _replace_qmark_placeholders(translated)
    return translated


def normalize_params(params: Sequence[Any] | Iterable[Any] | None) -> tuple[Any, ...]:
    if params is None:
        return ()
    if isinstance(params, tuple):
        return params
    if isinstance(params, list):
        return tuple(params)
    return tuple(params)


def is_insert_query(query: str) -> bool:
    return query.lstrip().upper().startswith("INSERT")