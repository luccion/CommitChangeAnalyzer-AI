from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from commit_change_analyzer.diffing import diff_tables
from commit_change_analyzer.git_ops import collect_commit_events, read_blob
from commit_change_analyzer.models import AnalysisReport, FileAnalysis
from commit_change_analyzer.normalize import load_tables, write_normalized_tables
from commit_change_analyzer.reporting import write_report
from commit_change_analyzer.rules import analyze_diffs


@dataclass(slots=True)
class AnalyzerConfig:
    repo: Path
    output_dir: Path
    since: str | None
    until: str | None
    base: str | None
    head: str
    mode: str


def run_analysis(config: AnalyzerConfig) -> dict[str, str]:
    commits, range_description = collect_commit_events(
        config.repo,
        since=config.since,
        until=config.until,
        base=config.base,
        head=config.head,
    )

    file_reports: list[FileAnalysis] = []
    warnings: list[str] = []
    key_changes: list[str] = []
    risks = []
    todos = []
    changed_file_count = sum(len(commit.changed_files) for commit in commits)

    if config.mode != "rule":
        warnings.append(f"Mode '{config.mode}' is not implemented yet; falling back to rule-only analysis.")

    artifact_root = config.output_dir / "artifacts"
    for commit in commits:
        for file_change in commit.changed_files:
            analysis = FileAnalysis(commit_id=commit.commit_id, file_change=file_change)
            if file_change.file_type == "other":
                analysis.warnings.append(f"{file_change.file_path}: skipped unsupported file type.")
                file_reports.append(analysis)
                warnings.extend(analysis.warnings)
                continue

            before_blob = read_blob(config.repo, file_change.before_ref)
            after_blob = read_blob(config.repo, file_change.after_ref)
            before_tables, before_warnings = load_tables(file_change.previous_path or file_change.file_path, file_change.file_type, before_blob or b"")
            after_tables, after_warnings = load_tables(file_change.file_path, file_change.file_type, after_blob or b"")
            analysis.warnings.extend(before_warnings)
            analysis.warnings.extend(after_warnings)

            if file_change.file_type == "excel":
                artifact_dir = artifact_root / commit.commit_id / Path(file_change.file_path).stem
                write_normalized_tables(before_tables, artifact_dir, "before")
                write_normalized_tables(after_tables, artifact_dir, "after")

            analysis.diffs = diff_tables(before_tables, after_tables)
            analysis.key_changes, analysis.risks, analysis.todos = analyze_diffs(
                file_change.file_path,
                analysis.diffs,
                analysis.warnings,
            )
            file_reports.append(analysis)
            warnings.extend(analysis.warnings)
            key_changes.extend(analysis.key_changes)
            risks.extend(analysis.risks)
            todos.extend(analysis.todos)

    analyzed_files = [item for item in file_reports if item.file_change.file_type != "other"]
    summary = (
        f"Analyzed {len(commits)} commit(s) and {len(analyzed_files)} supported file change(s), "
        f"producing {len(risks)} risk item(s) and {len(todos)} todo item(s)."
    )
    report = AnalysisReport(
        summary=summary,
        key_changes=dedupe(key_changes),
        risks=risks,
        todos=todos,
        metrics={
            "commit_count": len(commits),
            "changed_file_count": changed_file_count,
            "analyzed_file_count": len(analyzed_files),
            "diff_count": sum(len(item.diffs) for item in file_reports),
            "risk_count": len(risks),
            "todo_count": len(todos),
        },
        commits=commits,
        files=file_reports,
        warnings=dedupe(warnings),
        output_dir=str(config.output_dir),
    )
    return write_report(report, config.output_dir, range_description, config.mode)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
