# 工程目录规划

以下为建议目录结构，方便前后端分离开发、配置模型与本地 Ontop 测试：

```
make-r2rml/
|-- AGENTS.md
|-- docs/
|   |-- PRODUCT.md
|   `-- PROJECT_STRUCTURE.md
|-- frontend/
|   |-- README.md
|   |-- src/
|   `-- public/
|-- backend/
|   |-- README.md
|   |-- app/
|   |   |-- api/
|   |   |-- agents/
|   |   |-- services/
|   |   |-- models/
|   |   `-- utils/
|   |-- tests/
|   `-- requirements.txt
|-- services/
|   `-- ontop/
|       |-- README.md
|       |-- docker-compose.yml
|       `-- config/
|-- data/
|   |-- tbox/
|   |-- samples/
|   |-- mappings/
|   `-- abox/
|-- mock/
|   |-- rdfs/
|   `-- data/
|-- scripts/
`-- .env.example
```

## 目录说明
- `frontend/`：React 前端工程。
- `backend/`：Python 后端与智能体实现。
- `backend/app/agents/`：OpenAI Agents 框架与 R2RML Skill 的实现入口。
- `services/ontop/`：本地 Ontop 服务（Demo 用）。
- `data/`：样例数据与产物缓存目录。
- `mock/`：本地模型与 CSV 样例目录（不入库）。
- `.env.example`：模型与数据库连接配置模板（不含真实密钥）。

## 配置约定（建议）
- Qwen API key 通过环境变量注入，不提交仓库。
- JDBC 连接信息使用 `.env` 管理。
