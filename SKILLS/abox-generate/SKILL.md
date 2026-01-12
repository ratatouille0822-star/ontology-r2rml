---
name: abox-generate
description: 根据匹配结果与表格数据生成 ABox Turtle 内容。用于后端 /abox 接口生成。
---

# ABox 生成技能

## 目标
- 生成 ABox Turtle 内容并持久化输出文件。

## 输入
- 表格数据
- 映射配置
- base IRI
- 输出目录

## 输出
- turtle 内容与输出文件路径

## 实现
- 调用 `app.services.abox_generator.generate_abox`。
- 输出写入配置的数据目录。
