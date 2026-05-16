from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ai_client import load_api_config, run_remote_analysis
from diffing import diff_tables
from git_ops import collect_commit_comparison, read_blob
from models import AnalysisReport, FileAnalysis
from normalize import load_tables, write_normalized_tables
from reporting import build_diff_context, build_diff_markdown, build_prompt_text, write_report
from rules import analyze_diffs, load_rule_config


@dataclass(slots=True)
class AnalyzerConfig:
    repo: Path
    output_dir: Path
    since: str | None
    until: str | None
    base: str | None
    head: str
    target_path: Path | None
    mode: str
    rules_config: Path | None


def run_analysis(config: AnalyzerConfig) -> dict[str, str]:
    rule_config = load_rule_config(config.repo, config.rules_config)
    comparison = collect_commit_comparison(
        config.repo,
        since=config.since,
        until=config.until,
        base=config.base,
        head=config.head,
        target_path=config.target_path,
    )

    file_reports: list[FileAnalysis] = []
    warnings: list[str] = []
    key_changes: list[str] = []
    changed_file_count = len(comparison.changed_files)

    if config.mode not in {"rule", "api"}:
        warnings.append(f"Mode '{config.mode}' is not implemented yet; falling back to rule-only analysis.")

    artifact_root = config.output_dir / "artifacts"
    for file_change in comparison.changed_files:
        analysis = FileAnalysis(commit_id=comparison.after.commit_id, file_change=file_change)
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
            artifact_dir = artifact_root / comparison.description / Path(file_change.file_path).stem
            write_normalized_tables(before_tables, artifact_dir, "before")
            write_normalized_tables(after_tables, artifact_dir, "after")

        analysis.diffs = diff_tables(before_tables, after_tables)
        analysis.key_changes = analyze_diffs(
            file_change.file_path,
            analysis.diffs,
            analysis.warnings,
            rule_config,
        )
        file_reports.append(analysis)
        warnings.extend(analysis.warnings)
        key_changes.extend(analysis.key_changes)

    analyzed_files = [item for item in file_reports if item.file_change.file_type != "other"]
    summary = f"Compared {comparison.description} across {len(analyzed_files)} supported file change(s)."
    report = AnalysisReport(
        summary=summary,
        key_changes=dedupe(key_changes),
        metrics={
            "commit_count": 2,
            "changed_file_count": changed_file_count,
            "analyzed_file_count": len(analyzed_files),
            "diff_count": sum(len(item.diffs) for item in file_reports),
        },
        commits=[comparison.before, comparison.after],
        files=file_reports,
        warnings=dedupe(warnings),
        output_dir=str(config.output_dir),
    )
    range_description = comparison.description
    if config.target_path is not None:
        range_description = f"{comparison.description} / path={config.target_path.as_posix()}"
    outputs = write_report(report, config.output_dir, range_description, config.mode)

    if config.mode == "api":
        try:
            api_config = load_api_config(config.repo)
            prompt_text = build_prompt_text(range_description)
            diff_markdown = build_diff_markdown(report, range_description)
            diff_json_text = json.dumps(build_diff_context(report, range_description), ensure_ascii=False, indent=2)
            remote_result = run_remote_analysis(
                api_config,
                prompt_text=prompt_text,
                diff_markdown=diff_markdown,
                diff_json_text=diff_json_text,
                summary_text=report.summary,
            )
            ai_markdown_path = config.output_dir / "ai-analysis.md"
            ai_json_path = config.output_dir / "ai-analysis.json"
            ai_markdown_path.write_text(str(remote_result["content"]), encoding="utf-8")
            ai_json_path.write_text(json.dumps(remote_result, ensure_ascii=False, indent=2), encoding="utf-8")
            outputs = write_report(report, config.output_dir, range_description, config.mode, ai_result=remote_result)
            outputs["ai_markdown"] = str(ai_markdown_path)
            outputs["ai_json"] = str(ai_json_path)
        except RuntimeError as error:
            warning_text = f"API analysis skipped: {error}"
            warnings.append(warning_text)
            report.warnings = dedupe(warnings)
            outputs = write_report(report, config.output_dir, range_description, config.mode)

    return outputs


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
