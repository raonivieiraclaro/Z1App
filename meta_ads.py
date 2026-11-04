"""Administrative campaign drafts and explicitly confirmed PAUSED campaigns only."""
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

router = APIRouter()
OBJECTIVES = {
    "OUTCOME_LEADS": "Cadastros e leads",
    "OUTCOME_TRAFFIC": "Tráfego",
    "OUTCOME_ENGAGEMENT": "Engajamento e mensagens",
    "OUTCOME_SALES": "Vendas",
    "OUTCOME_AWARENESS": "Reconhecimento",
    "OUTCOME_APP_PROMOTION": "Promoção de aplicativo",
}
CATEGORIES = {"CREDIT", "EMPLOYMENT", "HOUSING", "ISSUES_ELECTIONS_POLITICS", "FINANCIAL_PRODUCTS_SERVICES"}


def settings():
    account = os.getenv("META_AD_ACCOUNT_ID", "").strip().removeprefix("act_")
    version = os.getenv("META_ADS_GRAPH_VERSION", "v25.0").strip()
    if not re.fullmatch(r"v[0-9]+\.0", version):
        version = "v25.0"
    return account, os.getenv("META_ADS_ACCESS_TOKEN", "").strip(), version


def db_connection():
    path = os.getenv("Z1_ADS_DB_PATH", "/tmp/z1_ads.sqlite3")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS campaign_drafts (
        id TEXT PRIMARY KEY, created_at INTEGER NOT NULL, account_id TEXT NOT NULL,
        payload TEXT NOT NULL, notes TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'draft',
        campaign_id TEXT, issue TEXT)""")
    return db


def same_origin(req: Request):
    origin = req.headers.get("origin", "")
    expected = f"{req.url.scheme}://{req.url.netloc}"
    if origin != expected:
        raise HTTPException(403, "Origem da solicitação inválida. Reabra o painel e tente novamente.")


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    objective: Literal["OUTCOME_LEADS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT", "OUTCOME_SALES", "OUTCOME_AWARENESS", "OUTCOME_APP_PROMOTION"]
    special_ad_categories: list[str] = Field(default_factory=list, max_length=5)
    notes: str = Field(default="", max_length=2000)


class ConfirmInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_paused_creation: StrictBool


def payload_for(data: DraftInput):
    if any(item not in CATEGORIES for item in data.special_ad_categories):
        raise HTTPException(422, "Categoria especial inválida.")
    return {
        "name": data.name,
        "objective": data.objective,
        "status": "PAUSED",
        "special_ad_categories": sorted(set(data.special_ad_categories)),
        "is_adset_budget_sharing_enabled": False,
    }


def public_draft(row):
    return {"id": row["id"], "created_at": row["created_at"], "account_id": row["account_id"],
            "campaign": json.loads(row["payload"]), "notes": row["notes"], "state": row["state"],
            "campaign_id": row["campaign_id"], "issue": row["issue"]}


def graph_request(method, path, payload=None):
    """No retries on writes. Never expose provider responses, request URLs or tokens."""
    _, token, version = settings()
    body = None
    if payload is not None:
        form = {k: json.dumps(v) if isinstance(v, (list, dict, bool)) else str(v) for k, v in payload.items()}
        body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(f"https://graph.facebook.com/{version}/{path}", data=body,
                                 method=method, headers={"Authorization": "Bearer " + token,
                                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read(512000))
        if not isinstance(result, dict) or "error" in result:
            raise ValueError("Invalid Graph response")
        return result
    except urllib.error.HTTPError as exc:
        # A server error can be ambiguous after a write. Do not retry it.
        if exc.code >= 500:
            raise HTTPException(502, "Resultado da Meta não confirmado. Confira o Gerenciador de Anúncios antes de tentar criar outra campanha.") from None
        raise HTTPException(424, "A Meta recusou a solicitação. Confira token, permissões ads_management e acesso à conta de anúncios.") from None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise HTTPException(502, "Não foi possível confirmar o resultado na Meta. Confira o Gerenciador de Anúncios antes de tentar novamente.") from None


@router.get("/api/ads/status")
def ads_status():
    account, token, version = settings()
    return {"configured": bool(re.fullmatch(r"[0-9]+", account) and token),
            "account_id": account if re.fullmatch(r"[0-9]+", account) else "",
            "token_present": bool(token), "graph_version": version, "creation_status": "PAUSED",
            "activation_available": False}


@router.get("/api/ads/account")
def ads_account():
    account, token, _ = settings()
    if not token or not re.fullmatch(r"[0-9]+", account):
        raise HTTPException(409, "Configure META_ADS_ACCESS_TOKEN e META_AD_ACCOUNT_ID no Render.")
    data = graph_request("GET", f"act_{account}?fields=id,name,currency,account_status")
    if data.get("id") != f"act_{account}":
        raise HTTPException(502, "A Meta não confirmou a conta configurada.")
    return {key: data.get(key) for key in ("id", "name", "currency", "account_status")}


@router.get("/api/ads/drafts")
def drafts():
    with db_connection() as db:
        rows = db.execute("SELECT * FROM campaign_drafts ORDER BY created_at DESC, rowid DESC LIMIT 100").fetchall()
    return {"drafts": [public_draft(row) for row in rows]}


@router.post("/api/ads/drafts")
def save_draft(data: DraftInput, req: Request):
    same_origin(req)
    payload = payload_for(data)
    account, _, _ = settings()
    draft_id = str(uuid.uuid4())
    with db_connection() as db:
        db.execute("INSERT INTO campaign_drafts(id,created_at,account_id,payload,notes) VALUES(?,?,?,?,?)",
                   (draft_id, int(time.time()), account, json.dumps(payload), data.notes))
        row = db.execute("SELECT * FROM campaign_drafts WHERE id=?", (draft_id,)).fetchone()
    return public_draft(row)


@router.post("/api/ads/drafts/{draft_id}/create")
def create_paused(draft_id: str, data: ConfirmInput, req: Request):
    same_origin(req)
    if data.confirm_paused_creation is not True:
        raise HTTPException(422, "Confirme a criação pausada após revisar a campanha.")
    account, token, _ = settings()
    if not token or not re.fullmatch(r"[0-9]+", account):
        raise HTTPException(409, "Credenciais de anúncios pendentes no Render. O rascunho foi preservado.")
    # Claim the attempt atomically, across processes. A repeated request cannot create again.
    with db_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM campaign_drafts WHERE id=?", (draft_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Rascunho não encontrado.")
        if row["state"] == "created":
            return public_draft(row)
        if row["state"] != "draft":
            raise HTTPException(409, "Este envio já foi tentado. Confira o resultado na Meta; o sistema não repetirá a criação.")
        if row["account_id"] != account:
            raise HTTPException(409, "A conta foi alterada. Gere e revise um novo rascunho.")
        campaign = json.loads(row["payload"])
        # Enforce again at the transport boundary, regardless of the stored draft.
        campaign["status"] = "PAUSED"
        db.execute("UPDATE campaign_drafts SET state='submitting' WHERE id=?", (draft_id,))
    try:
        result = graph_request("POST", f"act_{account}/campaigns", campaign)
        campaign_id = str(result.get("id", ""))
        if not re.fullmatch(r"[0-9]+", campaign_id):
            raise HTTPException(502, "A Meta não retornou um ID de campanha. Confira o Gerenciador antes de criar outra.")
    except HTTPException as exc:
        state = "failed" if exc.status_code == 424 else "unknown"
        with db_connection() as db:
            db.execute("UPDATE campaign_drafts SET state=?,issue=? WHERE id=?", (state, exc.detail, draft_id))
        raise
    except Exception:
        with db_connection() as db:
            db.execute("UPDATE campaign_drafts SET state='unknown',issue=? WHERE id=?",
                       ("Resultado não confirmado; confira a Meta antes de tentar novamente.", draft_id))
        raise HTTPException(502, "Resultado não confirmado; confira o Gerenciador de Anúncios.") from None
    with db_connection() as db:
        db.execute("UPDATE campaign_drafts SET state='created',campaign_id=? WHERE id=?", (campaign_id, draft_id))
        row = db.execute("SELECT * FROM campaign_drafts WHERE id=?", (draft_id,)).fetchone()
    return public_draft(row)


@router.get("/meta-ads", response_class=HTMLResponse)
def ads_page():
    return Path(__file__).with_name("meta_ads.html").read_text(encoding="utf-8")
