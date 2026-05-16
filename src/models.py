from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FileChange:
    file_path: str
    file_type: str
    before_ref: str | None
    after_ref: str | None
    status: str
    previous_path: str | None = None


@dataclass(slots=True)
class CommitEvent:
    commit_id: str
    author: str
    time: str
    message: str
    changed_files: list[FileChange]


@dataclass(slots=True)
class CommitComparison:
    before: CommitEvent
    after: CommitEvent
    changed_files: list[FileChange]
    description: str


@dataclass(slots=True)
class NormalizedRow:
    row_key: str
    values: dict[str, str]
    source_index: int


@dataclass(slots=True)
class NormalizedTable:
    source_path: str
    table_name: str
    headers: list[str]
    rows: list[NormalizedRow]
    key_field: str | None


@dataclass(slots=True)
class StructuredDiff:
    table: str
    row_key: str
    column: str
    before_value: str
    after_value: str
    change_type: str


@dataclass(slots=True)
class RiskItem:
    risk_type: str
    severity: str
    confidence: float
    evidence: str
    impact: str


@dataclass(slots=True)
class TodoItem:
    title: str
    priority: str
    owner_hint: str
    due_hint: str
    action: str
    verify_steps: str
    evidence: str


@dataclass(slots=True)
class FileAnalysis:
    commit_id: str
    file_change: FileChange
    diffs: list[StructuredDiff] = field(default_factory=list)
    key_changes: list[str] = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    todos: list[TodoItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AnalysisReport:
    summary: str
    key_changes: list[str]
    risks: list[RiskItem]
    todos: list[TodoItem]
    metrics: dict[str, Any]
    commits: list[CommitEvent]
    files: list[FileAnalysis]
    warnings: list[str] = field(default_factory=list)
    output_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.output_dir:
            data["output_dir"] = str(Path(self.output_dir))
        return data
