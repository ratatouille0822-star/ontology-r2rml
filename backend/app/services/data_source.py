from io import BytesIO
from typing import List
from datetime import date, datetime
from pathlib import Path
import math

import numpy as np
import pandas as pd


def parse_tabular_files(files: list[tuple[str, bytes]]) -> List[dict]:
    if not files:
        raise ValueError('未提供数据文件')

    tables: list[dict] = []

    for filename, content in files:
        lower = filename.lower()
        if lower.endswith('.csv'):
            df = _read_csv(content)
            table_name = _table_name_from_file(filename)
            tables.append(_build_table(table_name, df))
        elif lower.endswith(('.xlsx', '.xls')):
            tables.extend(_read_excel_tables(filename, content))
        else:
            raise ValueError(f'不支持的文件类型: {filename}')

    return tables


def _normalize_rows(rows: list[dict]) -> list[dict]:
    return [{key: _normalize_value(value) for key, value in row.items()} for row in rows]


def _normalize_value(value):
    if value is None:
        return None
    try:
        flag = pd.isna(value)
    except Exception:
        flag = False
    if isinstance(flag, (bool, np.bool_)) and flag:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        return str(value)
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, bytes):
        return value.decode(errors='ignore')
    return value


def _read_csv(content: bytes) -> pd.DataFrame:
    stream = BytesIO(content)
    return pd.read_csv(stream)


def _read_excel_tables(filename: str, content: bytes) -> list[dict]:
    stream = BytesIO(content)
    tables: list[dict] = []
    excel = pd.ExcelFile(stream)
    for sheet_name in excel.sheet_names:
        df = pd.read_excel(excel, sheet_name=sheet_name)
        table_name = f"{_table_name_from_file(filename)}::{sheet_name}"
        tables.append(_build_table(table_name, df))
    return tables


def _build_table(table_name: str, df: pd.DataFrame) -> dict:
    df = df.astype(object).where(pd.notnull(df), None)
    fields = [str(col) for col in df.columns]
    rows = _normalize_rows(df.to_dict(orient='records'))
    return {
        'name': table_name,
        'fields': fields,
        'sample_rows': rows[:5],
        'rows': rows,
    }


def _table_name_from_file(filename: str) -> str:
    path = Path(filename)
    return path.stem or path.name
