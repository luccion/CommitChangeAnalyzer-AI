from __future__ import annotations

from commit_change_analyzer.models import NormalizedTable, StructuredDiff


def _row_map(table: NormalizedTable) -> dict[str, dict[str, str]]:
    return {row.row_key: row.values for row in table.rows}


def diff_tables(before: list[NormalizedTable], after: list[NormalizedTable]) -> list[StructuredDiff]:
    before_map = {table.table_name: table for table in before}
    after_map = {table.table_name: table for table in after}
    diffs: list[StructuredDiff] = []
    for table_name in sorted(set(before_map) | set(after_map)):
        before_table = before_map.get(table_name)
        after_table = after_map.get(table_name)
        if before_table is None and after_table is not None:
            diffs.append(
                StructuredDiff(
                    table=table_name,
                    row_key="*",
                    column="*",
                    before_value="",
                    after_value="present",
                    change_type="table_added",
                )
            )
            continue
        if before_table is not None and after_table is None:
            diffs.append(
                StructuredDiff(
                    table=table_name,
                    row_key="*",
                    column="*",
                    before_value="present",
                    after_value="",
                    change_type="table_removed",
                )
            )
            continue
        assert before_table is not None and after_table is not None
        before_headers = set(before_table.headers)
        after_headers = set(after_table.headers)
        for column in sorted(after_headers - before_headers):
            diffs.append(
                StructuredDiff(
                    table=table_name,
                    row_key="*",
                    column=column,
                    before_value="",
                    after_value="present",
                    change_type="column_added",
                )
            )
        for column in sorted(before_headers - after_headers):
            diffs.append(
                StructuredDiff(
                    table=table_name,
                    row_key="*",
                    column=column,
                    before_value="present",
                    after_value="",
                    change_type="column_removed",
                )
            )
        before_rows = _row_map(before_table)
        after_rows = _row_map(after_table)
        all_headers = list(dict.fromkeys([*before_table.headers, *after_table.headers]))
        for row_key in sorted(set(before_rows) | set(after_rows)):
            before_row = before_rows.get(row_key)
            after_row = after_rows.get(row_key)
            if before_row is None and after_row is not None:
                diffs.append(
                    StructuredDiff(
                        table=table_name,
                        row_key=row_key,
                        column="*",
                        before_value="",
                        after_value="present",
                        change_type="row_added",
                    )
                )
                continue
            if before_row is not None and after_row is None:
                diffs.append(
                    StructuredDiff(
                        table=table_name,
                        row_key=row_key,
                        column="*",
                        before_value="present",
                        after_value="",
                        change_type="row_deleted",
                    )
                )
                continue
            assert before_row is not None and after_row is not None
            for header in all_headers:
                before_value = before_row.get(header, "")
                after_value = after_row.get(header, "")
                if before_value != after_value:
                    diffs.append(
                        StructuredDiff(
                            table=table_name,
                            row_key=row_key,
                            column=header,
                            before_value=before_value,
                            after_value=after_value,
                            change_type="cell_changed",
                        )
                    )
    return diffs
