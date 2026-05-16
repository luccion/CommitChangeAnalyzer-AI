# CommitChangeAnalyzer-AI

一个基于 Python 的提交分析工具，用于对目标时间附近的两个最近提交做直接对比，重点处理 Excel 等二进制文件的变更。

1. 采集目标 period 起点和终点附近最接近边界的两个提交，并直接比较它们的文件变更。
2. 还原变更前后版本，支持 CSV、JSON、文本以及 `.xlsx/.xlsm` Excel 文件。
3. 将 Excel 规范化为稳定 CSV 制品。
4. 生成结构化 diff、风险项和 TODO 列表。
5. 输出 Markdown 报告、结构化 diff 上下文和 AI prompt 文件。（或者你可以直接使用根目录下的 `.prompt.md`）
6. 可选通过 `api` 模式把 `.prompt.md` 和 diff context 交给远程 AI 生成最终分析结果。

## 环境
- Python 3.10+
- Git 命令行工具（确保 `git` 命令可用）
- 对于 Excel 文件的分析，需要安装 `openpyxl` 和 `pandas`：

如果你要启用远程 AI 分析：

1. 复制 [.env.example](.env.example) 为 `.env`
2. 填入 `AI_API_KEY`，必要时补充 `AI_BASE_URL` 和 `AI_MODEL`
3. 使用 `--mode api` 运行

如果你要放进 GitHub Actions：

1. 在仓库 Secrets 中配置 `AI_API_KEY`
2. 按需配置 `AI_BASE_URL`、`AI_MODEL`、`AI_TEMPERATURE`、`AI_TIMEOUT_SECONDS`
3. 使用仓库内置的 [commit-change-analysis.yml](.github/workflows/commit-change-analysis.yml)


## 快速开始（Windows） 

1. 将`analyze_commits_single.py`粘贴到你的项目中
2. 进入项目（分析目标）目录
3. 运行分析脚本：
```bash
python analyze_commits_single.py
```
默认会分析所选范围的起点和终点提交，并把结果输出到 `output\`。

## 使用
1. 你可以将本仓库完整地粘贴到你的项目中，然后执行 `analyze_commits.py` 来运行分析。脚本会自动采集目标时间范围内的两个边界提交，并生成分析结果。
2. 如果你想在本地生成分析脚本，可以先克隆这个仓库，然后运行：

```bash
python tools/export_single_file.py --output analyze_commits_single.py
```

然后把 `analyze_commits_single.py` 复制到目标仓库即可运行（`.prompt.md` 会在导出时自动内嵌）。

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
- `--mode api`：在本地生成客观 diff 后，调用远程 OpenAI-compatible API 生成 AI 分析结果。


```bash
python analyze_commits.py --since 2026-05-01 --until 2026-05-16 --path assets/excel --output-dir .\output
```

启用远程 AI 分析：

```bash
python analyze_commits.py --since 2026-05-01 --until 2026-05-16 --mode api
```

## GitHub Actions

仓库已内置 [commit-change-analysis.yml](.github/workflows/commit-change-analysis.yml)，支持两种触发方式：

- `pull_request`：自动分析 PR 的 base/head，并把 `ai-analysis.md` 回写到 PR 评论中。
- `workflow_dispatch`：手动运行，可选传入 `base`、`head` 和 `target_path`。

这个 workflow 会：

1. 检出完整历史。
2. 安装 Python 和项目依赖。
3. 以 `--mode api` 运行分析。
4. 上传 `output/` 目录为 artifact。
5. 在 PR 中创建或更新一条固定评论，集中展示 AI 分析结果。

## 输出内容

工具默认生成以下产物：

- `analysis-report.md`：给人阅读的分析报告。
- `analysis-report.json`：给程序消费的完整结构化结果。
- `todo-list.json`：标准化 TODO 列表。
- `diff-context.md`：客观的结构化 diff 上下文，适合交给 AI 分析。
- `diff-context.json`：与 diff-context.md 对应的结构化 JSON。
- `ai-prompt.md`：配套的 AI 分析提示词。
- `ai-analysis.md`：远程 AI 返回的最终分析结果，仅在 `--mode api` 成功时生成。
- `ai-analysis.json`：远程 AI 的原始返回和元数据，仅在 `--mode api` 成功时生成。
- `artifacts/`：仅保留这两个提交对比所需的 Excel 规范化 CSV 制品。

当指定 `--path` 时，上述产物只会覆盖该路径下的变更内容。

当 `--mode api` 成功时，`analysis-report.md` 和 `analysis-report.json` 也会并入远程 AI 的最终分析结果，便于集中查看。

其中 `analysis-report.md` 只保留一句话级别的客观摘要和最少元信息；风险和 TODO 主要交给 `ai-prompt.md` 对应的 AI 分析流程生成。