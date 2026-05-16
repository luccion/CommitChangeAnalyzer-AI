from __future__ import annotations

import argparse
from pathlib import Path

from orchestrator import AnalyzerConfig, run_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-change-analyzer",
        description="Analyze commit changes and generate a markdown report plus a todo list.",
    )
    parser.add_argument("--repo", default=".", help="Repository path to analyze.")
    parser.add_argument("--output-dir", default="output", help="Directory for generated reports.")
    parser.add_argument("--since", help="Git --since expression, such as '2026-05-01'.")
    parser.add_argument("--until", help="Git --until expression, such as '2026-05-16'.")
    parser.add_argument("--base", help="Base commit or branch for range analysis.")
    parser.add_argument("--head", default="HEAD", help="Head commit or branch for range analysis.")
    parser.add_argument(
        "--path",
        dest="target_path",
        help="Repository subdirectory or file path to include in the analysis.",
    )
    parser.add_argument(
        "--mode",
        choices=["rule", "agent", "api"],
        default="rule",
        help="Analysis mode: rule for local-only output, api for remote AI analysis after local diff generation.",
    )
    parser.add_argument(
        "--rules-config",
        help="Path to a JSON rules config file. Defaults to commit-change-rules.json in the repo root when present.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AnalyzerConfig(
        repo=Path(args.repo).resolve(),
        output_dir=Path(args.output_dir).resolve(),
        since=args.since,
        until=args.until,
        base=args.base,
        head=args.head,
        target_path=Path(args.target_path) if args.target_path else None,
        mode=args.mode,
        rules_config=Path(args.rules_config) if args.rules_config else None,
    )
    outputs = run_analysis(config)
    print("Analysis completed.")
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0
