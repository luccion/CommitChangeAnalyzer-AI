# CommitChangeAnalyzer-AI

一个基于 Python 的提交分析工具，用于对目标时间附近的两个最近提交做直接对比，重点处理 Excel 等二进制文件的变更。

1. 采集目标 period 起点和终点附近最接近边界的两个提交，并直接比较它们的文件变更。
2. 还原变更前后版本，支持 CSV、JSON、文本以及 `.xlsx/.xlsm` Excel 文件。
3. 将 Excel 规范化为稳定 CSV 制品。
4. 生成结构化 diff、风险项和 TODO 列表。
5. 输出 Markdown 报告、结构化 diff 上下文和 AI prompt 文件。（或者你可以直接使用根目录下的 `.prompt.md`）

## 环境
- Python 3.10+
- Git 命令行工具（确保 `git` 命令可用）
- 对于 Excel 文件的分析，需要安装 `openpyxl` 和 `pandas`：


## 快速开始（Windows） 
1. 将本仓库完整地粘贴到你的项目中
2. 进入项目（分析目标）目录
3. 运行分析脚本：
```bash
python path/to/analyze_commits.py
```

默认会分析所选范围的起点和终点提交，并把结果输出到 `output\`。

如果你更喜欢安装后再运行，也可以：

```bash
python -m pip install -e .
python -m commit_change_analyzer
```

## 参数

- `--base`：分析范围的起点提交（默认为 Git 仓库当前 HEAD 的父提交）。
- `--head`：分析范围的终点提交（默认为 Git 仓库当前 HEAD）。
- `--since`：分析范围的起点时间（格式为 YYYY-MM-DD）。
- `--until`：分析范围的终点时间（格式为 YYYY-MM-DD）。
- `--path`：只分析特定目录或文件的变更。
- `--output-dir`：指定输出目录（默认为当前目录下的 `output\`）。


```bash
python analyze_commits.py --since 2026-05-01 --until 2026-05-16 --path assets/excel --output-dir .\output
```

## 输出内容

工具默认生成以下产物：

- `analysis-report.md`：给人阅读的分析报告。
- `analysis-report.json`：给程序消费的完整结构化结果。
- `todo-list.json`：标准化 TODO 列表。
- `diff-context.md`：客观的结构化 diff 上下文，适合交给 AI 分析。
- `diff-context.json`：与 diff-context.md 对应的结构化 JSON。
- `ai-prompt.md`：配套的 AI 分析提示词。
- `artifacts/`：仅保留这两个提交对比所需的 Excel 规范化 CSV 制品。

当指定 `--path` 时，上述产物只会覆盖该路径下的变更内容。

其中 `analysis-report.md` 只保留一句话级别的客观摘要和最少元信息；风险和 TODO 主要交给 `ai-prompt.md` 对应的 AI 分析流程生成。