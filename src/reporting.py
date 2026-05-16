from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import cast

from models import AnalysisReport


def _markdown_escape(value: str) -> str:
    return value.replace("\n", "<br>").replace("|", "\\|")


def _build_diff_context(report: AnalysisReport, range_description: str) -> dict[str, object]:
    commits = report.commits[:2]
    before_commit = commits[0] if len(commits) > 0 else None
    after_commit = commits[1] if len(commits) > 1 else None

    def commit_summary(commit: object | None) -> dict[str, object] | None:
        if commit is None:
            return None
        return {
            "commit_id": getattr(commit, "commit_id", None),
            "author": getattr(commit, "author", None),
            "time": getattr(commit, "time", None),
            "message": getattr(commit, "message", None),
        }

    return {
        "range_description": range_description,
        "comparison": {
            "before": commit_summary(before_commit),
            "after": commit_summary(after_commit),
        },
        "metrics": report.metrics,
        "warnings": report.warnings,
        "files": [
            {
                "commit_id": file_report.commit_id,
                "file_path": file_report.file_change.file_path,
                "previous_path": file_report.file_change.previous_path,
                "file_type": file_report.file_change.file_type,
                "status": file_report.file_change.status,
                "before_ref": file_report.file_change.before_ref,
                "after_ref": file_report.file_change.after_ref,
                "warnings": file_report.warnings,
                "diffs": [asdict(diff) for diff in file_report.diffs],
            }
            for file_report in report.files
            if file_report.file_change.file_type != "other"
        ],
    }


def _build_diff_markdown(report: AnalysisReport, range_description: str) -> str:
    context = _build_diff_context(report, range_description)
    comparison = cast(dict[str, object], context["comparison"])
    before_commit = cast(dict[str, object] | None, comparison.get("before"))
    after_commit = cast(dict[str, object] | None, comparison.get("after"))
    before_line = "-"
    after_line = "-"
    if isinstance(before_commit, dict):
        before_line = f"{before_commit.get('commit_id', '-')}: {before_commit.get('message', '-') or '-'}"
    if isinstance(after_commit, dict):
        after_line = f"{after_commit.get('commit_id', '-')}: {after_commit.get('message', '-') or '-'}"

    sections: list[str] = [
        "# 客观 Diff 上下文",
        "",
        "## 比较范围",
        "",
        f"- 范围：{range_description}",
        f"- 变更前提交：{before_line}",
        f"- 变更后提交：{after_line}",
        "",
        "## 统计",
        "",
        f"- commit_count: {report.metrics.get('commit_count', 0)}",
        f"- changed_file_count: {report.metrics.get('changed_file_count', 0)}",
        f"- analyzed_file_count: {report.metrics.get('analyzed_file_count', 0)}",
        f"- diff_count: {report.metrics.get('diff_count', 0)}",
        f"- risk_count: {report.metrics.get('risk_count', 0)}",
        f"- todo_count: {report.metrics.get('todo_count', 0)}",
        "",
        "## 文件级差异",
        "",
    ]

    files = cast(list[dict[str, object]], context["files"])
    if files:
        for file_entry in files:
            sections.extend(
                [
                    f"### {file_entry.get('file_path', '-')}",
                    "",
                    f"- 类型：{file_entry.get('file_type', '-')}",
                    f"- 状态：{file_entry.get('status', '-')}",
                    f"- 旧路径：{file_entry.get('previous_path') or '-'}",
                    f"- before_ref：{file_entry.get('before_ref') or '-'}",
                    f"- after_ref：{file_entry.get('after_ref') or '-'}",
                ]
            )
            warnings = cast(list[object], file_entry.get("warnings") or [])
            if warnings:
                sections.append("- 警告：")
                sections.extend(f"  - {str(warning)}" for warning in warnings)
            diffs = cast(list[dict[str, object]], file_entry.get("diffs") or [])
            if diffs:
                sections.extend([
                    "",
                    "| table | row_key | column | change_type | before_value | after_value |",
                    "| --- | --- | --- | --- | --- | --- |",
                ])
                for diff in diffs:
                    sections.append(
                        "| {table} | {row_key} | {column} | {change_type} | {before_value} | {after_value} |".format(
                            table=_markdown_escape(str(diff.get("table", "-"))),
                            row_key=_markdown_escape(str(diff.get("row_key", "-"))),
                            column=_markdown_escape(str(diff.get("column", "-"))),
                            change_type=_markdown_escape(str(diff.get("change_type", "-"))),
                            before_value=_markdown_escape(str(diff.get("before_value", ""))),
                            after_value=_markdown_escape(str(diff.get("after_value", ""))),
                        )
                    )
            else:
                sections.append("- 无结构化差异。")
            sections.append("")
    else:
        sections.append("- 无可分析的结构化文件变更。")

    if report.warnings:
        sections.extend(["## 全局警告", ""])
        sections.extend(f"- {warning}" for warning in report.warnings)
        sections.append("")

    return "\n".join(sections).rstrip() + "\n"


def _build_prompt_text(range_description: str) -> str:
    prompt_source = Path(__file__).resolve().parents[2] / ".prompt.md"
    if prompt_source.exists():
        return prompt_source.read_text(encoding="utf-8")
    return f"# AI 分析提示\n\n请基于 {range_description} 的客观 diff 上下文进行语义分析。\n"


def write_report(report: AnalysisReport, output_dir: Path, range_description: str, mode: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "analysis-report.md"
    json_path = output_dir / "analysis-report.json"
    todo_path = output_dir / "todo-list.json"
    diff_markdown_path = output_dir / "diff-context.md"
    diff_json_path = output_dir / "diff-context.json"
    prompt_path = output_dir / "ai-prompt.md"

    markdown = f"""# 提交变更分析报告

{report.summary}

分析范围：`{range_description}`
运行模式：`{mode}`
指标：commits={report.metrics.get('commit_count', 0)}, changed_files={report.metrics.get('changed_file_count', 0)}, analyzed_files={report.metrics.get('analyzed_file_count', 0)}, diffs={report.metrics.get('diff_count', 0)}

AI 中间产物：{diff_markdown_path.name}、{diff_json_path.name}、{prompt_path.name}
"""
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    todo_path.write_text(
        json.dumps([asdict(todo) for todo in report.todos], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    diff_markdown_path.write_text(_build_diff_markdown(report, range_description), encoding="utf-8")
    diff_json_path.write_text(json.dumps(_build_diff_context(report, range_description), ensure_ascii=False, indent=2), encoding="utf-8")
    prompt_path.write_text(_build_prompt_text(range_description), encoding="utf-8")
    return {
        "markdown": str(markdown_path),
        "json": str(json_path),
        "todo_json": str(todo_path),
        "diff_markdown": str(diff_markdown_path),
        "diff_json": str(diff_json_path),
        "prompt": str(prompt_path),
    }
