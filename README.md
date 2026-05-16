# CommitChangeAnalyzer-AI

一个基于 Python 的提交分析工具，用于直接对比目标时间附近的两个最近提交，重点处理 Excel 等二进制文件的变更。

1. 采集目标 period 起点和终点附近最接近边界的两个提交，并直接比较它们的文件变更。
2. 还原变更前后版本，支持 CSV、JSON、文本以及 `.xlsx/.xlsm` Excel 文件。
3. 将 Excel 规范化为稳定 CSV 制品。
4. 生成结构化 diff 和客观变更摘要。
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
- `--rules-config`：指定项目级规则配置 JSON；如果仓库根目录存在 `commit-change-rules.json` 或 `.commit-change-rules.json`，会自动加载。

```bash
python analyze_commits.py --since 2026-05-01 --until 2026-05-16 --path assets/excel --output-dir .\output
```

启用远程 AI 分析：

```bash
python analyze_commits.py --since 2026-05-01 --until 2026-05-16 --mode api
```

使用项目级规则配置：

```bash
python analyze_commits.py --since 2026-05-01 --until 2026-05-16 --rules-config .\commit-change-rules.json
```

## 可配置规则

你可以在目标仓库根目录放置 `commit-change-rules.json`，或者通过 `--rules-config` 显式指定。配置文件目前支持两类扩展：

1. 覆盖或增删字段词典，用于调整“标识字段”“数值平衡字段”等启发式识别。
2. 注入项目级摘要规则，用于按表名、列名、变更类型、文件路径等条件命中更贴近项目语义的 key change 话术。

如果你想直接复制一份起步模板，可以使用仓库根目录的 `commit-change-rules.example.json`，把它复制到目标项目后改名为 `commit-change-rules.json` 再按项目实际字段调整。

示例：

```json
{
  "field_hints": {
    "identifier": {
      "add": ["quest_id", "stage_id"]
    },
    "balance": {
      "add": ["stamina", "crit", "cooldown"],
      "remove": ["score"]
    }
  },
  "rules": [
    {
      "name": "Quest reward change",
      "match": {
        "file_path_hints": ["quest"],
        "column_hints": ["reward", "drop"],
        "change_types": ["cell_changed"],
        "numeric_only": true
      },
      "key_change_template": "{file_path} 的表 {table} 行 {row_key} 的任务奖励字段 {column} 从 {before_value} 变为 {after_value}。"
    }
  ]
}
```

说明：

- `field_hints.identifier` 和 `field_hints.balance` 支持三种写法：直接传数组；使用 `add/remove` 在默认词典上增删；使用 `replace` 完全覆盖默认词典。
- `rules[].match` 当前支持 `change_types`、`column_hints`、`table_hints`、`row_key_hints`、`file_path_hints`、`numeric_only`、`before_empty`、`after_empty`。
- 自定义规则优先于内置启发式规则命中，适合为项目内的专有表和字段补充更准确的摘要话术。

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

另外已内置 [release.yml](.github/workflows/release.yml)，用于发布版本：

- `push tag (v*)`：自动导出 `analyze_commits_single.py` 并创建 GitHub Release。
- `workflow_dispatch`：手动指定 tag 发布。

使用 release workflow 前请推送类似 `v0.1.1` 的 tag，或手动触发并填写 `tag`。
release 附件只会包含 `analyze_commits_single.py`，便于直接下载后粘贴到目标仓库使用。

## 输出内容

工具默认生成以下产物：

- `analysis-report.md`：给人阅读的分析报告。
- `analysis-report.json`：给程序消费的完整结构化结果。
- `diff-context.md`：客观的结构化 diff 上下文，适合交给 AI 分析。
- `diff-context.json`：与 diff-context.md 对应的结构化 JSON。
- `ai-prompt.md`：配套的 AI 分析提示词。
- `ai-analysis.md`：远程 AI 返回的最终分析结果，仅在 `--mode api` 成功时生成。
- `ai-analysis.json`：远程 AI 的原始返回和元数据，仅在 `--mode api` 成功时生成。
- `artifacts/`：仅保留这两个提交对比所需的 Excel 规范化 CSV 制品。

当指定 `--path` 时，上述产物只会覆盖该路径下的变更内容。

当 `--mode api` 成功时，`analysis-report.md` 和 `analysis-report.json` 也会并入远程 AI 的最终分析结果，便于集中查看。

其中 `analysis-report.md` 只保留一句话级别的客观摘要和最少元信息；更细的语义解释主要交给 `ai-prompt.md` 对应的 AI 分析流程生成。

## 注意事项

在使用mode api时，谨慎划定评估时间范围和文件范围，过大的范围可能导致你的Token焚烧殆尽。

## 后续规划

1. 提升规则准确率。当前默认规则仍以字段词典和启发式匹配为主，后续会继续增强项目级领域规则、降低误报和漏报。
2. 补齐 `agent` 模式。CLI 已暴露 `rule/agent/api` 三种模式，但目前真正完整的是 `rule` 和 `api`，后续会把 `agent` 模式做成独立可用能力。
