"""Agent service: FastAPI wrapper around the LangGraph decision graph.

POST /decide  — run one case through the graph; may pause at human_review
POST /resume  — deliver the human's approve/reject and continue from checkpoint
GET  /health  — liveness

Checkpoints live in PostgresSaver on the shared database (DATABASE_URL), so a
paused case survives an agent restart. Without DATABASE_URL (unit tests, dev)
an in-memory checkpointer is used and pauses do not survive restarts.
"""

import os
from pathlib import Path
from urllib.parse import quote

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from graph.build import build_graph
from graph.llm import DecideLLM

POLICY_PATH = Path(__file__).parent / "policy.yaml"


def _resolve_database_url() -> str:
    """Where to keep LangGraph checkpoints.

    Accepts either a psycopg URL (AGENT_DATABASE_URL, or DATABASE_URL when the
    agent has its own) or the backend's JDBC-style DATABASE_URL plus
    DATABASE_USER / DATABASE_PASSWORD — so one shared .env drives both
    services without the operator maintaining two spellings of the same
    connection. Empty string means "no durable checkpoints".
    """
    explicit = os.environ.get("AGENT_DATABASE_URL", "").strip()
    if explicit:
        return explicit

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith("jdbc:"):
        return url

    base = url[len("jdbc:"):]                       # postgresql://host:port/db
    user = os.environ.get("DATABASE_USER", "").strip()
    password = os.environ.get("DATABASE_PASSWORD", "").strip()
    if user and "://" in base:
        scheme, rest = base.split("://", 1)
        return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{rest}"
    return base


DATABASE_URL = _resolve_database_url()

app = FastAPI(title="recovery-agent")
decide_llm = DecideLLM()   # uses Gemini when GOOGLE_API_KEY is set, else rule fallback


def _make_checkpointer():
    if not DATABASE_URL:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg import Connection
    from psycopg.rows import dict_row
    conn = Connection.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
    saver = PostgresSaver(conn)
    saver.setup()   # idempotent: creates checkpoint tables if missing
    return saver


checkpointer = _make_checkpointer()
graph = build_graph(checkpointer)


def load_policy() -> dict:
    """Read policy.yaml on every call — hot-reloadable by design."""
    with POLICY_PATH.open() as f:
        return yaml.safe_load(f)


def _config(case_id: str) -> dict:
    return {"configurable": {"policy": load_policy(),
                             "llm": decide_llm,
                             "thread_id": case_id}}


def _summary(case_id: str, values: dict, paused: bool, trace: list) -> dict:
    return {
        "case_id": case_id,
        "status": "WAITING_APPROVAL" if paused else values.get("status"),
        "paused": paused,
        "diagnosis": values.get("diagnosis"),
        "recovered_paise": values.get("recovered_paise", 0),
        "actions": values.get("actions", []),
        "close_reason": values.get("close_reason", ""),
        "escalated": values.get("escalated", False),
        "trace": trace,
    }


class DecideRequest(BaseModel):
    case_id: str
    amount_paise: int
    error_reason: str
    opted_out: bool = False
    attempts: int = 0
    contacts_made: int = 0
    auto_approve: bool = False           # batch mode: simulate an approving human
    now: str = Field(default="", description="ISO timestamp override for determinism")
    ev_stats: dict | None = Field(default=None,
                                  description="learned Beta-Bernoulli counts from the backend: "
                                              "{cause: {action: [alpha, beta]}}")


class ResumeRequest(BaseModel):
    case_id: str
    approved: bool


@app.get("/health")
def health():
    return {"status": "ok", "durable_checkpoints": bool(DATABASE_URL)}


@app.post("/decide")
def decide(req: DecideRequest):
    # each /decide is a fresh run for this case: clear any stale thread state
    # (e.g. from a previous batch) so trace/actions reducers start empty.
    try:
        checkpointer.delete_thread(req.case_id)
    except Exception:
        pass

    initial = {
        "case_id": req.case_id,
        "amount_paise": req.amount_paise,
        "error_reason": req.error_reason,
        "opted_out": req.opted_out,
        "attempts": req.attempts,
        "contacts_made": req.contacts_made,
        "auto_approve": req.auto_approve,
        "now_iso": req.now,
        "actions": [],
        "trace": [],
    }
    config = _config(req.case_id)
    config["configurable"]["ev_stats"] = req.ev_stats
    result = graph.invoke(initial, config)
    paused = "__interrupt__" in result
    return _summary(req.case_id, result, paused, result.get("trace", []))


@app.post("/resume")
def resume(req: ResumeRequest):
    from langgraph.types import Command

    config = _config(req.case_id)
    snapshot = graph.get_state(config)
    if snapshot is None or not snapshot.next:
        raise HTTPException(status_code=409,
                            detail=f"case {req.case_id} is not paused for approval")

    seen = len(snapshot.values.get("trace", []))
    result = graph.invoke(Command(resume=req.approved), config)
    paused = "__interrupt__" in result
    # return only the NEW trace entries so the backend never double-logs
    new_trace = result.get("trace", [])[seen:]
    return _summary(req.case_id, result, paused, new_trace)
