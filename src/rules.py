from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from models import StructuredDiff

DEFAULT_ID_HINTS = ("id", "key", "code")
DEFAULT_BALANCE_HINTS = ("hp", "attack", "damage", "drop", "reward", "rate", "ratio", "cost", "price", "exp", "score")
DEFAULT_RULE_FILENAMES = ("commit-change-rules.json", ".commit-change-rules.json")


@dataclass(slots=True)
class RuleMatch:
    change_types: tuple[str, ...] = ()
    column_hints: tuple[str, ...] = ()
    table_hints: tuple[str, ...] = ()
    row_key_hints: tuple[str, ...] = ()
    file_path_hints: tuple[str, ...] = ()
    numeric_only: bool = False
    before_empty: bool | None = None
    after_empty: bool | None = None


@dataclass(slots=True)
class CustomRule:
    name: str
    matcher: RuleMatch
    key_change_template: str


@dataclass(slots=True)
class RuleConfig:
    identifier_hints: tuple[str, ...]
    balance_hints: tuple[str, ...]
    custom_rules: tuple[CustomRule, ...] = ()
    source_path: Path | None = None


def default_rule_config() -> RuleConfig:
    return RuleConfig(
        identifier_hints=DEFAULT_ID_HINTS,
        balance_hints=DEFAULT_BALANCE_HINTS,
    )


def load_rule_config(repo_root: Path, config_path: Path | None = None) -> RuleConfig:
    resolved_path = _resolve_rule_config_path(repo_root, config_path)
    if resolved_path is None:
        return default_rule_config()

    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RuntimeError(f"Unable to read rules config '{resolved_path}': {error}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Rules config '{resolved_path}' is not valid JSON: {error}") from error

    if not isinstance(payload, dict):
        raise RuntimeError(f"Rules config '{resolved_path}' must contain a JSON object.")

    config = RuleConfig(
        identifier_hints=_load_hint_group(payload.get("field_hints"), "identifier", DEFAULT_ID_HINTS),
        balance_hints=_load_hint_group(payload.get("field_hints"), "balance", DEFAULT_BALANCE_HINTS),
        custom_rules=_load_custom_rules(payload.get("rules")),
        source_path=resolved_path,
    )
    return config


def _resolve_rule_config_path(repo_root: Path, config_path: Path | None) -> Path | None:
    if config_path is not None:
        candidate = config_path if config_path.is_absolute() else repo_root / config_path
        resolved = candidate.resolve()
        if not resolved.exists():
            raise RuntimeError(f"Rules config '{resolved}' does not exist.")
        return resolved

    for filename in DEFAULT_RULE_FILENAMES:
        candidate = (repo_root / filename).resolve()
        if candidate.exists():
            return candidate
    return None


def _load_hint_group(payload: object, group_name: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
    if payload is None:
        return defaults
    if not isinstance(payload, dict):
        raise RuntimeError("'field_hints' must be a JSON object.")
    group = payload.get(group_name)
    if group is None:
        return defaults
    if isinstance(group, list):
        return _normalize_string_list(group, f"field_hints.{group_name}")
    if not isinstance(group, dict):
        raise RuntimeError(f"'field_hints.{group_name}' must be an array or object.")

    values = list(defaults)
    replace_values = group.get("replace")
    if replace_values is not None:
        values = list(_normalize_string_list(replace_values, f"field_hints.{group_name}.replace"))
    for value in _normalize_string_list(group.get("add", []), f"field_hints.{group_name}.add"):
        if value not in values:
            values.append(value)
    remove_values = set(_normalize_string_list(group.get("remove", []), f"field_hints.{group_name}.remove"))
    return tuple(value for value in values if value not in remove_values)


def _load_custom_rules(payload: object) -> tuple[CustomRule, ...]:
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise RuntimeError("'rules' must be an array.")

    rules: list[CustomRule] = []
    for index, raw_rule in enumerate(payload):
        if not isinstance(raw_rule, dict):
            raise RuntimeError(f"rules[{index}] must be a JSON object.")
        name = _require_string(raw_rule, "name", f"rules[{index}]")
        matcher = _load_matcher(raw_rule.get("match"), f"rules[{index}].match")
        key_change_template = _require_string(raw_rule, "key_change_template", f"rules[{index}]")
        rules.append(
            CustomRule(
                name=name,
                matcher=matcher,
                key_change_template=key_change_template,
            )
        )
    return tuple(rules)


def _load_matcher(payload: object, path: str) -> RuleMatch:
    if payload is None:
        return RuleMatch()
    if not isinstance(payload, dict):
        raise RuntimeError(f"'{path}' must be a JSON object.")
    return RuleMatch(
        change_types=_normalize_string_list(payload.get("change_types", []), f"{path}.change_types"),
        column_hints=_normalize_string_list(payload.get("column_hints", []), f"{path}.column_hints"),
        table_hints=_normalize_string_list(payload.get("table_hints", []), f"{path}.table_hints"),
        row_key_hints=_normalize_string_list(payload.get("row_key_hints", []), f"{path}.row_key_hints"),
        file_path_hints=_normalize_string_list(payload.get("file_path_hints", []), f"{path}.file_path_hints"),
        numeric_only=_optional_bool(payload.get("numeric_only"), f"{path}.numeric_only") or False,
        before_empty=_optional_bool(payload.get("before_empty"), f"{path}.before_empty"),
        after_empty=_optional_bool(payload.get("after_empty"), f"{path}.after_empty"),
    )

def _normalize_string_list(values: object, path: str) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise RuntimeError(f"'{path}' must be an array of strings.")
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"'{path}[{index}]' must be a non-empty string.")
        lowered = value.strip().lower()
        if lowered not in normalized:
            normalized.append(lowered)
    return tuple(normalized)


def _require_string(payload: dict[str, Any], key: str, path: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"'{path}.{key}' must be a non-empty string.")
    return value.strip()


def _optional_bool(value: object, path: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise RuntimeError(f"'{path}' must be a boolean.")
    return value


def _contains_hint(name: str, hints: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in hints)


def _is_number(value: str) -> bool:
    if not value:
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False
def _transition(before_value: str, after_value: str) -> str:
    before_text = before_value or "空"
    after_text = after_value or "空"
    return f"从 {before_text} 变为 {after_text}"


def analyze_diffs(
    file_path: str,
    diffs: list[StructuredDiff],
    warnings: list[str],
    rule_config: RuleConfig | None = None,
) -> list[str]:
    config = rule_config or default_rule_config()
    key_changes: list[str] = []

    for diff in diffs:
        custom_rule = _match_custom_rule(file_path, diff, config.custom_rules)
        if custom_rule is not None:
            key_changes.append(_render_change(custom_rule.key_change_template, file_path, diff))
            continue

        if diff.change_type in {"table_added", "table_removed"}:
            if diff.change_type == "table_added":
                key_changes.append(f"{file_path} 的表 {diff.table} 从不存在变为存在。")
            else:
                key_changes.append(f"{file_path} 的表 {diff.table} 从存在变为不存在。")
            continue
        if diff.change_type in {"column_added", "column_removed"}:
            if diff.change_type == "column_added":
                key_changes.append(f"{file_path} 的表 {diff.table} 字段 {diff.column} 从不存在变为存在。")
            else:
                key_changes.append(f"{file_path} 的表 {diff.table} 字段 {diff.column} 从存在变为不存在。")
            continue
        if diff.change_type == "row_deleted":
            key_changes.append(f"{file_path} 的表 {diff.table} 中的行 {diff.row_key} 从存在变为不存在。")
            continue
        if diff.change_type == "row_added":
            key_changes.append(f"{file_path} 的表 {diff.table} 中新增了行 {diff.row_key}。")
            continue
        if _contains_hint(diff.column, config.identifier_hints):
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的标识字段 {diff.column} {_transition(diff.before_value, diff.after_value)}。"
            )
            continue
        if diff.before_value and not diff.after_value:
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的字段 {diff.column} 从 {diff.before_value} 变为空。"
            )
            continue
        if _contains_hint(diff.column, config.balance_hints) and _is_number(diff.before_value) and _is_number(diff.after_value):
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的数值字段 {diff.column} {_transition(diff.before_value, diff.after_value)}。"
            )
            continue
        if _is_number(diff.before_value) and _is_number(diff.after_value):
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的字段 {diff.column} {_transition(diff.before_value, diff.after_value)}。"
            )

    for warning in warnings:
        key_changes.append(warning)
    return key_changes


def _match_custom_rule(file_path: str, diff: StructuredDiff, rules: tuple[CustomRule, ...]) -> CustomRule | None:
    for rule in rules:
        if _rule_matches(file_path, diff, rule.matcher):
            return rule
    return None


def _rule_matches(file_path: str, diff: StructuredDiff, matcher: RuleMatch) -> bool:
    if matcher.change_types and diff.change_type not in matcher.change_types:
        return False
    if matcher.column_hints and not _contains_hint(diff.column, matcher.column_hints):
        return False
    if matcher.table_hints and not _contains_hint(diff.table, matcher.table_hints):
        return False
    if matcher.row_key_hints and not _contains_hint(diff.row_key, matcher.row_key_hints):
        return False
    if matcher.file_path_hints and not _contains_hint(file_path, matcher.file_path_hints):
        return False
    if matcher.numeric_only and not (_is_number(diff.before_value) and _is_number(diff.after_value)):
        return False
    if matcher.before_empty is not None and matcher.before_empty != (not bool(diff.before_value)):
        return False
    if matcher.after_empty is not None and matcher.after_empty != (not bool(diff.after_value)):
        return False
    return True


def _render_change(template: str, file_path: str, diff: StructuredDiff) -> str:
    return template.format_map(
        {
            "file_path": file_path,
            "table": diff.table,
            "row_key": diff.row_key,
            "column": diff.column,
            "before_value": diff.before_value or "空",
            "after_value": diff.after_value or "空",
            "change_type": diff.change_type,
        }
    )
