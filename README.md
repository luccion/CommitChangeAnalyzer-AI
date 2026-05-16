# CommitChangeAnalyzer-AI

一个基于 Python 的提交分析工具，用于分析某个时间段内的提交记录，重点处理 Excel 等二进制文件的变更。

当前仓库已提供一个可运行的 MVP，覆盖以下主流程：

1. 采集指定提交范围内的提交和文件变更。
2. 还原变更前后版本，支持 CSV、JSON、文本以及 `.xlsx/.xlsm` Excel 文件。
3. 将 Excel 规范化为稳定 CSV 制品。
4. 生成结构化 diff、风险项和 TODO 列表。
5. 输出 Markdown 报告和 JSON 结果文件。

## 快速开始（Windows）

最短路径（无需安装）：

```bash
python analyze_commits.py
```

默认会分析当前仓库最新一次提交，并把结果输出到 `output\`。

也可以双击或命令行运行：

```bash
run_analyzer.bat
```

如果你需要分析 Excel 文件，再安装额外依赖（推荐）：

```bash
python -m pip install openpyxl
```

或使用项目可选依赖：

```bash
python -m pip install ".[excel]"
```

如果你只是分析 CSV / JSON / 文本变更，则不需要先安装任何项目依赖。

## 使用方式

默认分析当前仓库最新一次提交：

```bash
python analyze_commits.py
```

按提交范围分析：

```bash
python analyze_commits.py --base main --head HEAD
```

按时间范围分析：

```bash
python analyze_commits.py --since 2026-05-01 --until 2026-05-16
```

指定输出目录：

```bash
python analyze_commits.py --output-dir .\output
```

如果你更喜欢安装后再运行，也可以：

```bash
python -m pip install -e .
python -m commit_change_analyzer
```

## 输出内容

工具默认生成以下产物：

- `analysis-report.md`：给人阅读的分析报告。
- `analysis-report.json`：给程序消费的完整结构化结果。
- `todo-list.json`：标准化 TODO 列表。
- `artifacts/`：Excel 规范化后的 CSV 制品。

## 当前 MVP 范围

- 已支持：提交采集、Excel 转 CSV、结构化 diff、规则分析、TODO 输出。
- 默认只建议使用规则分析；`agent/api` 仍保留兼容入口，但当前会退化为规则分析。
- 暂未支持：`.xls`、`.xlsb` 的结构化解析；这些文件会在报告中提示人工转换为 `.xlsx` 后重试。
