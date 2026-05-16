from __future__ import annotations

from collections import defaultdict

from models import RiskItem, StructuredDiff, TodoItem

ID_HINTS = ("id", "key", "code")
BALANCE_HINTS = ("hp", "attack", "damage", "drop", "reward", "rate", "ratio", "cost", "price", "exp", "score")


def _contains_hint(name: str, hints: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in hints)


def _is_number(value: str) -> bool:
    if not value:
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False


def _priority_for_severity(severity: str) -> str:
    return {
        "critical": "P0",
        "high": "P1",
        "medium": "P1",
        "low": "P2",
    }[severity]


def _transition(before_value: str, after_value: str) -> str:
    before_text = before_value or "空"
    after_text = after_value or "空"
    return f"从 {before_text} 变为 {after_text}"


def analyze_diffs(file_path: str, diffs: list[StructuredDiff], warnings: list[str]) -> tuple[list[str], list[RiskItem], list[TodoItem]]:
    key_changes: list[str] = []
    buckets: dict[str, dict[str, object]] = defaultdict(lambda: {"severity": "low", "count": 0, "evidence": []})

    def add_bucket(bucket: str, severity: str, evidence: str) -> None:
        current = buckets[bucket]
        current["count"] = int(current["count"]) + 1
        if severity_order(severity) > severity_order(str(current["severity"])):
            current["severity"] = severity
        evidence_list = current["evidence"]
        if isinstance(evidence_list, list) and len(evidence_list) < 3:
            evidence_list.append(evidence)

    for diff in diffs:
        evidence = f"{file_path}::{diff.table} row={diff.row_key} column={diff.column} type={diff.change_type}"
        if diff.change_type in {"table_added", "table_removed"}:
            add_bucket("schema-change", "high", evidence)
            if diff.change_type == "table_added":
                key_changes.append(f"{file_path} 的表 {diff.table} 从不存在变为存在。")
            else:
                key_changes.append(f"{file_path} 的表 {diff.table} 从存在变为不存在。")
            continue
        if diff.change_type in {"column_added", "column_removed"}:
            add_bucket("schema-change", "high", evidence)
            if diff.change_type == "column_added":
                key_changes.append(f"{file_path} 的表 {diff.table} 字段 {diff.column} 从不存在变为存在。")
            else:
                key_changes.append(f"{file_path} 的表 {diff.table} 字段 {diff.column} 从存在变为不存在。")
            continue
        if diff.change_type == "row_deleted":
            add_bucket("row-deletion", "high", evidence)
            key_changes.append(f"{file_path} 的表 {diff.table} 中的行 {diff.row_key} 从存在变为不存在。")
            continue
        if diff.change_type == "row_added":
            add_bucket("row-addition", "low", evidence)
            key_changes.append(f"{file_path} 的表 {diff.table} 中新增了行 {diff.row_key}。")
            continue
        if _contains_hint(diff.column, ID_HINTS):
            add_bucket("identifier-change", "critical", evidence)
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的标识字段 {diff.column} {_transition(diff.before_value, diff.after_value)}。"
            )
            continue
        if diff.before_value and not diff.after_value:
            add_bucket("value-cleared", "medium", evidence)
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的字段 {diff.column} 从 {diff.before_value} 变为空。"
            )
            continue
        if _contains_hint(diff.column, BALANCE_HINTS) and _is_number(diff.before_value) and _is_number(diff.after_value):
            add_bucket("balance-change", "high", evidence)
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的数值字段 {diff.column} {_transition(diff.before_value, diff.after_value)}。"
            )
            continue
        if _is_number(diff.before_value) and _is_number(diff.after_value):
            add_bucket("numeric-change", "medium", evidence)
            key_changes.append(
                f"{file_path} 的表 {diff.table} 行 {diff.row_key} 的字段 {diff.column} {_transition(diff.before_value, diff.after_value)}。"
            )

    for warning in warnings:
        add_bucket("unsupported-file", "medium", warning)
        key_changes.append(warning)

    risk_templates = {
        "schema-change": ("结构变更", "可能影响字段兼容性、下游读取逻辑或跨表引用关系。"),
        "row-deletion": ("数据删除", "可能导致引用失效、配置缺失或线上行为变化。"),
        "row-addition": ("新增数据", "需要确认新增配置是否已完成联调和验证。"),
        "identifier-change": ("标识字段变更", "主键或唯一标识变化可能导致引用链断裂。"),
        "value-cleared": ("关键值被清空", "清空字段可能触发默认值、空引用或配置异常。"),
        "balance-change": ("数值平衡变更", "数值调整可能影响战斗、掉落或奖励平衡。"),
        "numeric-change": ("数值字段变化", "数值变动需要业务确认是否符合预期。"),
        "unsupported-file": ("文件暂不可结构化分析", "该文件需要人工转换后再进行精确 diff。"),
    }

    todo_templates = {
        "schema-change": ("确认字段与下游兼容性", "数据负责人", "本次迭代内", "检查所有依赖该表的读取逻辑和脚本，确认字段新增/删除是否需要同步更新。", "在相关系统完成回归并确认读取成功。"),
        "row-deletion": ("核对删除数据的引用影响", "模块负责人", "提交前", "确认被删除数据是否仍被脚本、关卡或配置引用，必要时补迁移说明。", "搜索引用点并完成一次相关场景验证。"),
        "row-addition": ("确认新增数据接入链路", "策划/程序协作", "提测前", "检查新增配置是否已被代码、脚本或资源正确消费。", "验证新增配置在目标场景中生效。"),
        "identifier-change": ("核对主键或标识字段修改", "模块负责人", "立即", "确认所有引用该标识的表、脚本和逻辑是否同步更新。", "完成引用搜索并通过一次关键路径回归。"),
        "value-cleared": ("确认被清空字段是否允许为空", "数据负责人", "提测前", "核实清空字段是否有默认值保护，必要时补配置说明。", "确认运行时不会因空值报错或走错逻辑。"),
        "balance-change": ("复核关键数值调整", "策划负责人", "提测前", "复核数值改动意图，并安排相关玩法/掉落回归。", "通过目标场景的数值回归验证。"),
        "numeric-change": ("确认一般数值变更", "数据负责人", "提测前", "确认数值变更来源和预期影响，必要时补充说明。", "抽样核对变更后的行为与预期一致。"),
        "unsupported-file": ("转换不支持的 Excel 文件", "工具维护人", "下次分析前", "将不支持的文件格式转换为 .xlsx 并重新执行分析。", "重新生成结构化 diff 并确认无遗漏。"),
    }

    risks: list[RiskItem] = []
    todos: list[TodoItem] = []
    for bucket_name, bucket in sorted(buckets.items()):
        title, impact = risk_templates[bucket_name]
        evidence_lines = bucket["evidence"]
        evidence_text = "\n".join(f"- {line}" for line in evidence_lines) if isinstance(evidence_lines, list) else str(evidence_lines)
        severity = str(bucket["severity"])
        risks.append(
            RiskItem(
                risk_type=title,
                severity=severity,
                confidence=min(0.99, 0.55 + int(bucket["count"]) * 0.1),
                evidence=evidence_text,
                impact=impact,
            )
        )
        todo_title, owner_hint, due_hint, action, verify_steps = todo_templates[bucket_name]
        todos.append(
            TodoItem(
                title=todo_title,
                priority=_priority_for_severity(severity),
                owner_hint=owner_hint,
                due_hint=due_hint,
                action=action,
                verify_steps=verify_steps,
                evidence=evidence_text,
            )
        )
    return key_changes, risks, todos


def severity_order(severity: str) -> int:
    return {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }[severity]
