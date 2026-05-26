import asyncio
from typing import Dict
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from analyzer.metrics import analyze_code
import logging


logger = logging.getLogger(__name__)

app = FastAPI(title="Code Analyzer")


class AnalysisRequest(BaseModel):
    submission_id: int
    language: str
    source_code: str


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, submission_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[submission_id] = websocket

    def disconnect(self, submission_id: int):
        if submission_id in self.active_connections:
            del self.active_connections[submission_id]

    async def send(self, submission_id: int, message: dict):
        if submission_id in self.active_connections:
            websocket = self.active_connections[submission_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"WebSocket disconnected for submission {submission_id}. {e}")
                self.active_connections.pop(submission_id, None)


manager = ConnectionManager()


LANGUAGE_GROUPS: Dict[str, list[str]] = {
    "cpp":  ["CPP03", "CPP11", "CPP14", "CPP17", "CPP20", "CPP23"],
    "py":   ["PY2", "PY3"],
    "java": ["JAVA8", "JAVA11", "JAVA17"],
}

CODE_TO_FAMILY: Dict[str, str] = {
    code: family
    for family, codes in LANGUAGE_GROUPS.items()
    for code in codes
}


@app.post("/api/v1/analyze")
async def analyze(payload: AnalysisRequest, background_tasks: BackgroundTasks):
    family = CODE_TO_FAMILY.get(payload.language)
    if family is None:
        allowed = sorted(CODE_TO_FAMILY.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language '{payload.language}' is not supported. Allowed: {allowed}.",
        )

    try:
        metrics = await asyncio.to_thread(analyze_code, payload.source_code, family)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    background_tasks.add_task(manager.send, payload.submission_id, {"status": "ready"})
    
    return {"status": "success", "metrics": metrics}


@app.websocket("/ws/analysis/{submission_id}")
async def websocket_endpoint(websocket: WebSocket, submission_id: int):
    await manager.connect(submission_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(submission_id)