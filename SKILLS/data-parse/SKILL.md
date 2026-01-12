---
name: data-parse
description: 解析 CSV/XLSX 表格文件为标准化表结构，用于匹配。用于后端 /data/parse 上传解析。
---

# 数据解析技能

## 目标
- 解析一个或多个表格文件为表结构与样例行。

## 输入
- `(filename, bytes)` 列表

## 输出
- `tables`、`file_count`、`table_count`

## 实现
- 调用 `app.services.data_source.parse_tabular_files`。
- 规范化字段名与样例值。
- 对不支持的文件类型抛出错误。
