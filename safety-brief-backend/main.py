"""労働災害防止音声会話アプリ - FastAPI バックエンド

作業内容を受け取り、類似の過去災害事例を検索したうえで
Claude に安全ブリーフィングを生成させる REST API。
"""

import logging
import os
import sys
import time
from datetime import datetime
from difflib import SequenceMatcher
from typing import List, Optional

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
API_PORT = int(os.getenv("API_PORT", "8000"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
SENTENCE_MODEL_NAME = os.getenv(
    "SENTENCE_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"
)
CLAUDE_TIMEOUT_SECONDS = 5.0

# --- logging: normal logs -> stdout, errors -> stderr -------------------

logger = logging.getLogger("safety_brief")
logger.setLevel(LOG_LEVEL)
logger.propagate = False

_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
)

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_formatter)
_stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setFormatter(_formatter)
_stderr_handler.setLevel(logging.WARNING)

logger.addHandler(_stdout_handler)
logger.addHandler(_stderr_handler)

# --- ダミー災害DB --------------------------------------------------------

INCIDENT_DB = [
    {
        "date": "2023-12-15",
        "facility": "建設現場 A",
        "work_type": "足場組立",
        "description": "手すり未設置の足場から転落",
        "severity": "fatal",
        "preventive": "ハーネス必須、手すり設置確認",
    },
    {
        "date": "2022-08-20",
        "facility": "工場 B",
        "work_type": "足場組立",
        "description": "足場の固定不十分で崩壊",
        "severity": "injury",
        "preventive": "固定金具の3点以上確保",
    },
    {
        "date": "2023-03-02",
        "facility": "建設現場 C",
        "work_type": "高所作業",
        "description": "安全帯未使用で作業床から転落",
        "severity": "fatal",
        "preventive": "安全帯（フルハーネス型）の常時使用を徹底",
    },
    {
        "date": "2021-11-10",
        "facility": "工場 D",
        "work_type": "重機操作",
        "description": "クレーン旋回範囲内への立入りで接触",
        "severity": "injury",
        "preventive": "旋回範囲の立入禁止措置と誘導員配置",
    },
    {
        "date": "2022-05-27",
        "facility": "建設現場 E",
        "work_type": "電気工事",
        "description": "活線作業中の感電",
        "severity": "fatal",
        "preventive": "作業前の停電確認と検電の徹底",
    },
    {
        "date": "2023-09-08",
        "facility": "工場 F",
        "work_type": "足場解体",
        "description": "解体順序を誤り足場が倒壊",
        "severity": "injury",
        "preventive": "解体手順書に基づく段階的な作業",
    },
]

# --- 埋め込みモデル（遅延ロード、失敗時はキーワード類似度にフォールバック） --

_embedding_model = None
_embedding_model_load_failed = False
_incident_embeddings = None


def _get_embedding_model():
    global _embedding_model, _embedding_model_load_failed
    if _embedding_model is not None or _embedding_model_load_failed:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(SENTENCE_MODEL_NAME)
        logger.info("Loaded sentence-transformers model: %s", SENTENCE_MODEL_NAME)
    except Exception as exc:  # noqa: BLE001 - model load can fail many ways
        logger.error("Failed to load embedding model, falling back to keyword similarity: %s", exc)
        _embedding_model_load_failed = True
        _embedding_model = None
    return _embedding_model


def _get_incident_embeddings(model):
    global _incident_embeddings
    if _incident_embeddings is None:
        texts = [f"{inc['work_type']} {inc['description']}" for inc in INCIDENT_DB]
        _incident_embeddings = model.encode(texts)
    return _incident_embeddings


def _cosine_similarities(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
    return matrix_norm @ query_norm


def _keyword_score(query: str, incident: dict) -> float:
    text = f"{incident['work_type']} {incident['description']}"
    return SequenceMatcher(None, query, text).ratio()


def search_similar_incidents(work_description: str, top_k: int = 5) -> List[dict]:
    model = _get_embedding_model()
    if model is not None:
        query_vec = model.encode([work_description])[0]
        matrix = _get_incident_embeddings(model)
        sims = _cosine_similarities(query_vec, matrix)
        ranked = sorted(zip(INCIDENT_DB, sims), key=lambda pair: -pair[1])
    else:
        ranked = sorted(
            ((inc, _keyword_score(work_description, inc)) for inc in INCIDENT_DB),
            key=lambda pair: -pair[1],
        )
    return [inc for inc, _score in ranked[:top_k]]


# --- Claude 連携 ----------------------------------------------------------

_claude_client = None
_claude_client_init_failed = False


def _get_claude_client():
    global _claude_client, _claude_client_init_failed
    if _claude_client is not None or _claude_client_init_failed:
        return _claude_client
    if not CLAUDE_API_KEY:
        logger.error("CLAUDE_API_KEY is not set")
        _claude_client_init_failed = True
        return None
    try:
        import anthropic

        _claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialize Claude client: %s", exc)
        _claude_client_init_failed = True
        _claude_client = None
    return _claude_client


def build_prompt(work_description: str, incidents: List[dict]) -> str:
    incidents_text = "\n".join(
        f"- {inc['date']} {inc['facility']} ({inc['work_type']}): "
        f"{inc['description']} [重大度: {inc['severity']}] "
        f"再発防止策: {inc['preventive']}"
        for inc in incidents
    )
    return (
        "【過去の類似災害事例】\n"
        f"{incidents_text}\n\n"
        "【これからの作業】\n"
        f"{work_description}\n\n"
        "この作業に関する危険性と安全ポイントを、"
        "実務的で簡潔（2分程度の長さ）に説明してください。"
        "技術用語は説明付きで。"
    )


def build_fallback_text(work_description: str, incidents: List[dict]) -> str:
    top = incidents[0] if incidents else None
    if top is None:
        return (
            f"「{work_description}」に関する安全ブリーフィングを生成できませんでした。"
            "作業前に元請・安全担当者へ確認してください。"
        )
    preventives = "、".join(dict.fromkeys(inc["preventive"] for inc in incidents))
    return (
        f"この作業の危険性は、類似事例「{top['description']}」"
        f"（重大度: {top['severity']}）と同様のリスクが考えられます。"
        f"以下の安全ポイントを確認してください: {preventives}。"
        "（Claude API から応答を取得できなかったため、簡易フォールバック回答です）"
    )


def generate_safety_text(work_description: str, incidents: List[dict]):
    """Claude を呼び出して安全ブリーフィングを生成する。

    戻り値: (text, is_fallback, is_timeout)
    """
    client = _get_claude_client()
    if client is None:
        return build_fallback_text(work_description, incidents), True, False

    prompt = build_prompt(work_description, incidents)
    try:
        response = client.with_options(timeout=CLAUDE_TIMEOUT_SECONDS).messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text, False, False
    except Exception as exc:  # noqa: BLE001
        import anthropic

        is_timeout = isinstance(exc, (anthropic.APITimeoutError, TimeoutError))
        logger.error("Claude API call failed (timeout=%s): %s", is_timeout, exc)
        return build_fallback_text(work_description, incidents), True, is_timeout


# --- FastAPI アプリケーション ---------------------------------------------

app = FastAPI(title="労働災害防止音声会話アプリ - Safety Brief API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SafetyBriefRequest(BaseModel):
    work_description: str
    facility_type: Optional[str] = None


class IncidentOut(BaseModel):
    date: str
    description: str
    severity: str


class SafetyBriefResponse(BaseModel):
    text: str
    incident_count: int
    incidents: List[IncidentOut]


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}


@app.post("/safety-brief", response_model=SafetyBriefResponse)
def safety_brief(payload: SafetyBriefRequest):
    start = time.monotonic()
    work_description = payload.work_description.strip()

    if not work_description:
        logger.error("Empty work_description received")
        return JSONResponse(
            status_code=400,
            content={"detail": "work_description must not be empty"},
        )

    incidents = search_similar_incidents(work_description, top_k=5)
    text, is_fallback, is_timeout = generate_safety_text(work_description, incidents)

    response_body = SafetyBriefResponse(
        text=text,
        incident_count=len(incidents),
        incidents=[
            IncidentOut(
                date=inc["date"],
                description=inc["description"],
                severity=inc["severity"],
            )
            for inc in incidents
        ],
    )

    response_time = time.monotonic() - start
    logger.info(
        "timestamp=%s work_description=%r facility_type=%r response_time=%.3fs fallback=%s",
        datetime.utcnow().isoformat(),
        work_description,
        payload.facility_type,
        response_time,
        is_fallback,
    )

    if is_timeout:
        return JSONResponse(status_code=504, content=response_body.model_dump())

    return response_body


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
