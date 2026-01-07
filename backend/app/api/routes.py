from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.agents.r2rml_agent import R2RMLAgent
from app.models.schemas import AboxRequest, MatchRequest, MatchResponse, R2RmlRequest
from app.services.abox_generator import generate_abox
from app.services.data_source import parse_tabular_files
from app.services.r2rml_generator import generate_r2rml
from app.services.tbox_parser import parse_tbox
from app.utils.config import get_setting
from app.utils.version import BACKEND_VERSION

router = APIRouter()
agent = R2RMLAgent()


@router.get("/version")
async def version():
    return {"version": BACKEND_VERSION}


@router.post("/tbox/parse")
async def tbox_parse(file: UploadFile = File(...)):
    try:
        content = await file.read()
        properties = parse_tbox(content, file.filename)
        return {"properties": [item.model_dump() for item in properties]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/data/parse")
async def data_parse(files: list[UploadFile] = File(...)):
    try:
        file_items = []
        for file in files:
            content = await file.read()
            file_items.append((file.filename or "", content))

        columns, sample_rows, all_rows = parse_tabular_files(file_items)
        return {
            "columns": columns,
            "sample_rows": sample_rows,
            "rows": all_rows,
            "file_count": len(files),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/match", response_model=MatchResponse)
async def match_fields(payload: MatchRequest):
    matches = agent.match(payload.fields, payload.properties, payload.mode)
    return MatchResponse(matches=matches)


@router.post("/abox")
async def abox_generate(payload: AboxRequest):
    try:
        data_dir = get_setting("DATA_DIR", "./data")
        output_dir = str(Path(data_dir) / "abox")
        content, file_path = generate_abox(payload.rows, payload.mapping, payload.base_iri, output_dir)
        return {"format": "turtle", "content": content, "file_path": file_path}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/r2rml")
async def r2rml_generate(payload: R2RmlRequest):
    try:
        content = generate_r2rml(payload.mapping, payload.table_name, payload.base_iri)
        return {"format": "turtle", "content": content}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jdbc/test")
async def jdbc_test():
    raise HTTPException(status_code=501, detail="JDBC Demo 暂未启用。")
