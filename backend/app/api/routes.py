import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.agents.skill_dispatcher import SkillDispatcher
from app.models.schemas import AboxRequest, MatchRequest, MatchResponse, R2RmlRequest
from app.utils.version import BACKEND_VERSION

router = APIRouter()
dispatcher = SkillDispatcher()
logger = logging.getLogger(__name__)


@router.get("/version")
async def version():
    return {"version": BACKEND_VERSION}


@router.post("/tbox/parse")
async def tbox_parse(file: UploadFile = File(...)):
    try:
        content = await file.read()
        result = await dispatcher.parse_tbox(content, file.filename)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/data/parse")
async def data_parse(files: list[UploadFile] = File(...)):
    try:
        file_items = []
        for file in files:
            content = await file.read()
            file_items.append((file.filename or "", content))

        return await dispatcher.parse_data(file_items)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/match", response_model=MatchResponse)
async def match_fields(payload: MatchRequest):
    try:
        matches = await dispatcher.match(payload.properties, payload.tables, payload.mode, payload.threshold)
        return MatchResponse(matches=matches)
    except Exception as exc:
        logger.exception("匹配失败")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/abox")
async def abox_generate(payload: AboxRequest):
    try:
        result = await dispatcher.generate_abox(
            payload.tables,
            payload.mapping,
            payload.base_iri,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/r2rml")
async def r2rml_generate(payload: R2RmlRequest):
    try:
        result = await dispatcher.generate_r2rml(payload.mapping, payload.table_name, payload.base_iri)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jdbc/test")
async def jdbc_test():
    raise HTTPException(status_code=501, detail="JDBC Demo 暂未启用。")
