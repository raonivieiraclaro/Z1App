"""Official Meta webhooks and opt-in WhatsApp replies. Configure secrets in Render."""
import os
import hmac
import hashlib
import json
import asyncio
import urllib.request
import urllib.error
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from consultor import answer

router = APIRouter()
def configured(name):
    return bool(os.getenv(name, "").strip())

def valid_signature(raw, header):
    secret = os.getenv("META_APP_SECRET", "")
    if not secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)

@router.get("/webhooks/meta")
async def verify(req: Request):
    p = req.query_params
    token = os.getenv("META_VERIFY_TOKEN", "")
    if token and p.get("hub.mode") == "subscribe" and hmac.compare_digest(p.get("hub.verify_token", ""), token):
        return PlainTextResponse(p.get("hub.challenge", ""))
    return PlainTextResponse("Verification failed", status_code=403)

def send_whatsapp(phone_id, recipient, text):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    allowed_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    if not token or not allowed_id or phone_id != allowed_id:
        return False
    payload = {"messaging_product":"whatsapp", "to":recipient, "type":"text",
               "text":{"preview_url":False,"body":text[:3500]}}
    url = "https://graph.facebook.com/" + os.getenv("META_GRAPH_VERSION", "v22.0") + "/" + allowed_id + "/messages"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False

async def process_inbound(payload):
    if payload.get("object") != "whatsapp_business_account":
        return
    for entry in payload.get("entry", [])[:10]:
        for change in entry.get("changes", [])[:10]:
            value = change.get("value", {})
            phone_id = str(value.get("metadata", {}).get("phone_number_id", ""))
            for msg in value.get("messages", [])[:10]:
                # Respond only to user-initiated text messages. No cold outreach.
                if msg.get("type") != "text" or not msg.get("from") or not msg.get("id"):
                    continue
                prompt = str(msg.get("text", {}).get("body", "")).strip()[:2000]
                if not prompt:
                    continue
                result = await answer([{"role":"user","content":prompt}])
                if not result.get("configured"):
                    continue
                reply = result.get("answer", "")
                if reply:
                    await asyncio.to_thread(send_whatsapp,phone_id,str(msg["from"]),reply)

@router.post("/webhooks/meta")
async def receive(req: Request):
    raw = await req.body()
    if len(raw) > 512000:
        return JSONResponse({"error":"Payload too large"},status_code=413)
    if not valid_signature(raw,req.headers.get("x-hub-signature-256", "")):
        return JSONResponse({"error":"Invalid signature"},status_code=403)
    try:
        payload = json.loads(raw)
    except ValueError:
        return JSONResponse({"error":"Invalid JSON"},status_code=400)
    # Instagram events accepted and authenticated; no messaging without approved API setup.
    if payload.get("object") not in ("whatsapp_business_account","instagram","page"):
        return JSONResponse({"error":"Unsupported object"},status_code=400)
    if payload.get("object") == "whatsapp_business_account" and os.getenv("Z1_WHATSAPP_AUTO_REPLY", "").lower() == "true":
        await process_inbound(payload)
    return {"received":True}

def integration_status():
    return {
        "meta_webhook":configured("META_APP_SECRET") and configured("META_VERIFY_TOKEN"),
        "whatsapp":all(configured(k) for k in ("META_APP_SECRET","META_VERIFY_TOKEN","WHATSAPP_ACCESS_TOKEN","WHATSAPP_PHONE_NUMBER_ID")),
        "instagram":False,
        "zyone_api":False,
        "zyone_registration_link":True
    }
