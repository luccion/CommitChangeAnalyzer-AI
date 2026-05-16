from __future__ import annotations

import argparse
from pathlib import Path

from commit_change_analyzer.orchestrator import AnalyzerConfig, run_analysis


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
        "--mode",
        choices=["rule", "agent", "api"],
        default="rule",
        help=argparse.SUPPRESS,
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
        mode=args.mode,
    )
    outputs = run_analysis(config)
    print("Analysis completed.")
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0
