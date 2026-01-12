---
name: tbox-parse
description: 解析 TBox 本体文件，产出类、数据属性、对象属性与 TTL 内容。用于后端 /tbox/parse 接口处理本体文件。
---

# TBox 解析技能

## 目标
- 将本体文件字节与文件名解析为结构化 TBox 输出。
- 输出 properties、classes、object_properties、ttl。

## 输入
- 本体文件 bytes
- 文件名

## 输出
- `properties`、`classes`、`object_properties`、`ttl`

## 实现
- 调用 `app.services.tbox_parser.parse_tbox`。
- 对无效或不支持的文件抛出错误。
