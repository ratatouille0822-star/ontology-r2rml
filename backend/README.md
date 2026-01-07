# 后端

FastAPI 服务：解析 TBox、解析数据源、字段匹配、生成 ABox/R2RML 输出。

## 启动
在项目根目录执行：
```
python3 -m venv .venv
cd backend
../.venv/bin/pip install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple
cp ../.env.example .env
../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 接口（开发态）
- `POST /api/tbox/parse` (multipart file)
- `POST /api/data/parse` (multipart files)
- `POST /api/match` (json)
- `POST /api/abox` (json)
- `POST /api/r2rml` (json)

## 配置
- 参考 `../.env.example`。
- 在 `backend/.env` 中配置 Qwen API Key。
