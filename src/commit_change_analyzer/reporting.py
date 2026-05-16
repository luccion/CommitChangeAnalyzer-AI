from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from commit_change_analyzer.models import AnalysisReport


def _markdown_escape(value: str) -> str:
    return value.replace("\n", "<br>").replace("|", "\\|")


def write_report(report: AnalysisReport, output_dir: Path, range_description: str, mode: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "analysis-report.md"
    json_path = output_dir / "analysis-report.json"
    todo_path = output_dir / "todo-list.json"

    risk_rows = "\n".join(
        f"| {risk.severity} | {_markdown_escape(risk.risk_type)} | {_markdown_escape(risk.impact)} | {_markdown_escape(risk.evidence)} |"
        for risk in report.risks
    ) or "| - | - | - | - |"
    todo_rows = "\n".join(
        f"| {todo.priority} | {_markdown_escape(todo.title)} | {_markdown_escape(todo.owner_hint)} | {_markdown_escape(todo.action)} | {_markdown_escape(todo.verify_steps)} |"
        for todo in report.todos
    ) or "| - | - | - | - | - |"
    key_changes = "\n".join(f"- {change}" for change in report.key_changes[:20]) or "- 无关键结构化变更。"
    warnings = "\n".join(f"- {warning}" for warning in report.warnings) or "- 无"

    markdown = f"""# 提交变更分析报告

## 概览

- 分析范围：`{range_description}`
- 运行模式：`{mode}`
- 摘要：{report.summary}
- 指标：commits={report.metrics.get('commit_count', 0)}, changed_files={report.metrics.get('changed_file_count', 0)}, analyzed_files={report.metrics.get('analyzed_file_count', 0)}, diffs={report.metrics.get('diff_count', 0)}, risks={report.metrics.get('risk_count', 0)}, todos={report.metrics.get('todo_count', 0)}

## 关键变更

{key_changes}

## 风险清单

| Severity | 风险类型 | 影响 | 证据 |
| --- | --- | --- | --- |
{risk_rows}

## TODO 清单

| Priority | 标题 | 责任提示 | 建议动作 | 验证步骤 |
| --- | --- | --- | --- | --- |
{todo_rows}

## 警告

{warnings}
"""
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    todo_path.write_text(
        json.dumps([asdict(todo) for todo in report.todos], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "markdown": str(markdown_path),
        "json": str(json_path),
        "todo_json": str(todo_path),
    }
