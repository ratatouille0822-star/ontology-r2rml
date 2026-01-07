# make-r2rml

一个 R2RML TBox -> ABox 的演示系统，包含 React 前端、Python 后端，以及可选的本地 Ontop 服务。

## 结构
- `frontend/`：React 前端。
- `backend/`：FastAPI 后端与智能体逻辑。
- `services/ontop/`：本地 Ontop 服务（Demo）。
- `data/`：样例数据与输出。

## 后端启动（已验证可用）
在项目根目录执行：
```
python3 -m venv .venv
cd backend
../.venv/bin/pip install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple
cp ../.env.example .env
../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：`http://127.0.0.1:8000/health`

## 前端启动
```
cd frontend
npm install
npm run dev
```

## Ontop（可选）
```
cd services/ontop
docker compose up -d
```

## 说明
- Qwen API Key 在 `backend/.env` 中配置。
- 未配置 Key 时，匹配会自动回退到启发式规则。
- CSV/XLSX 支持多文件或目录上传，字段会合并后统一匹配。
