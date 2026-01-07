from io import BytesIO
from typing import Tuple

import pandas as pd


def _read_dataframe(content: bytes, filename: str) -> pd.DataFrame:
    lower = filename.lower()
    stream = BytesIO(content)
    if lower.endswith('.csv'):
        return pd.read_csv(stream)
    if lower.endswith(('.xlsx', '.xls')):
        return pd.read_excel(stream)
    raise ValueError('不支持的文件类型')


def parse_tabular_files(files: list[tuple[str, bytes]]) -> Tuple[list[str], list[dict], list[dict]]:
    if not files:
        raise ValueError('未提供数据文件')

    columns: list[str] = []
    seen = set()
    all_rows: list[dict] = []
    sample_rows: list[dict] = []

    for filename, content in files:
        df = _read_dataframe(content, filename)
        df = df.where(pd.notnull(df), None)
        for col in df.columns:
            col_str = str(col)
            if col_str not in seen:
                seen.add(col_str)
                columns.append(col_str)

        rows = df.to_dict(orient='records')
        all_rows.extend(rows)
        sample_rows.extend(rows[:5])

    return columns, sample_rows, all_rows
