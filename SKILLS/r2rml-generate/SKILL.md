---
name: r2rml-generate
description: 根据所选表与映射配置生成 R2RML Turtle。用于后端 /r2rml 接口生成。
---

# R2RML 生成技能

## 目标
- 生成指定表的 R2RML Turtle 内容。

## 输入
- 映射配置
- 表名
- base IRI

## 输出
- turtle 内容

## 实现
- 调用 `app.services.r2rml_generator.generate_r2rml`。
