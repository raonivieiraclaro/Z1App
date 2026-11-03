import os
import time
import hmac
import hashlib
import base64
import secrets
import html
from urllib.parse import quote

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

app = FastAPI(title="Z1 Prospect IA")
CATALOG = "https://drive.google.com/file/d/1vu44BXv5hsItreNOfpU_AR6NK6lLrgiF/view?usp=drivesdk"
REGISTER = "https://escritorio.zyone.com.br/cadastro#?id=leticiajulia"
COOKIE_NAME = "z1_session"
SESSION_SECONDS = 12 * 60 * 60

def credentials():
    return os.getenv("Z1_ADMIN_USER", ""), os.getenv("Z1_ADMIN_PASSWORD", "")

def signing_key():
    user, password = credentials()
    return hashlib.sha256(("z1-session-v1:" + user + ":" + password).encode()).digest()

def sign(timestamp):
    return hmac.new(signing_key(), timestamp.encode(), hashlib.sha256).hexdigest()

def valid_session(value):
    if not value:
        return False
    try:
        timestamp, signature = value.split(".", 1)
        issued = int(timestamp)
        return (issued <= int(time.time()) and int(time.time()) - issued < SESSION_SECONDS
                and hmac.compare_digest(signature, sign(timestamp)))
    except (ValueError, TypeError):
        return False

def basic_auth_valid(req, user, password):
    header = req.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        return False
    try:
        raw = base64.b64decode(header[6:], validate=True).decode("utf-8")
        candidate_user, candidate_password = raw.split(":", 1)
        return (secrets.compare_digest(candidate_user, user)
                and secrets.compare_digest(candidate_password, password))
    except (ValueError, UnicodeError):
        return False

@app.middleware("http")
async def auth(req: Request, call_next):
    if req.url.path in ("/healthz", "/login"):
        return await call_next(req)
    user, password = credentials()
    if not user or not password:
        return HTMLResponse(
            "<html lang='pt-br'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<body style='font-family:sans-serif;padding:30px'>"
            "<h2>Configuração pendente</h2>"
            "<p>Defina Z1_ADMIN_USER e Z1_ADMIN_PASSWORD no menu Environment do Render e aguarde o deploy.</p>"
            "</body></html>", status_code=503)
    if valid_session(req.cookies.get(COOKIE_NAME)) or basic_auth_valid(req, user, password):
        return await call_next(req)
    return RedirectResponse("/login", status_code=303)

@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.get("/login", response_class=HTMLResponse)
def login_page(error: str = ""):
    user, password = credentials()
    configured = bool(user and password)
    note = ("<p style='color:#ffb3b3'>Usuário ou senha incorretos.</p>"
            if error else "")
    if not configured:
        note = "<p>Configure Z1_ADMIN_USER e Z1_ADMIN_PASSWORD em Environment no Render.</p>"
    return HTMLResponse("""<!doctype html><html lang="pt-br"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Entrar — Z1 Prospect IA</title>
<style>body{background:#111;color:#eee;font:16px system-ui;margin:0;padding:24px}
main{max-width:440px;margin:10vh auto}section{background:#222;padding:24px;border-radius:16px}
input{display:block;box-sizing:border-box;width:100%;padding:14px;margin:10px 0 18px;
background:#333;border:1px solid #777;border-radius:8px;color:#fff;font-size:16px}
button{width:100%;padding:14px;background:#d8ad4d;color:#111;font-size:17px;
font-weight:700;border:0;border-radius:8px}</style>
<main><section><h1>✨ Z1 Prospect IA</h1><p>Acesso administrativo</p>"""
+ note + """<form method="post" action="/login">
<label>Usuário<input name="username" autocomplete="username" required></label>
<label>Senha<input name="password" type="password" autocomplete="current-password" required></label>
<button type="submit">Entrar</button></form></section></main></html>""")

@app.post("/login")
async def login_submit(req: Request):
    user, password = credentials()
    form = await req.form()
    entered_user = str(form.get("username", ""))
    entered_password = str(form.get("password", ""))
    if not user or not password or not (secrets.compare_digest(entered_user, user)
                                      and secrets.compare_digest(entered_password, password)):
        return RedirectResponse("/login?error=1", status_code=303)
    timestamp = str(int(time.time()))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(COOKIE_NAME, timestamp + "." + sign(timestamp),
                        max_age=SESSION_SECONDS, secure=True, httponly=True,
                        samesite="lax", path="/")
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response

@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html lang="pt-br"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Z1 Prospect IA</title>
<style>body{font-family:system-ui;background:#111;color:#eee;margin:0;padding:24px}
main{max-width:680px;margin:auto}section{background:#222;padding:20px;border-radius:12px;margin:16px 0}
a{color:#e6b95b}input{box-sizing:border-box;width:100%;padding:10px;margin:6px 0;
background:#333;color:white;border:1px solid #777;border-radius:6px}
button{padding:12px;background:#e6b95b;border:0;border-radius:6px;color:#111}</style>
<main><h1>✨ Z1 Prospect IA</h1><p>Painel de demonstração — Zyone Cosméticos</p>
<p><a href="/logout">Sair da conta</a></p>
<section><h2>Catálogo</h2><a href='""" + html.escape(CATALOG, quote=True) + """'
target="_blank" rel="noopener">Abrir catálogo Zyone</a></section>
<section><h2>Link de cadastro</h2><a href='""" + html.escape(REGISTER, quote=True) + """'
target="_blank" rel="noopener">Abrir cadastro</a></section>
<section><h2>Configurações locais de links</h2>
<p>Os campos abaixo são temporários; não alteram os links do servidor.</p>
<label>Catálogo</label><input id="catalog" value='""" + html.escape(CATALOG, quote=True) + """'>
<label>Cadastro</label><input id="register" value='""" + html.escape(REGISTER, quote=True) + """'>
<button id="apply">Aplicar nesta tela</button><p id="links"></p></section>
<section><h2>Integrações</h2><p>Instagram, WhatsApp e escritório Zyone ainda não estão conectados.
Não insira tokens neste protótipo.</p></section>
<script>document.getElementById('apply').addEventListener('click',function(){
const target=document.getElementById('links');target.replaceChildren();
for(const [id,label] of [['catalog','Catálogo configurado'],['register','Cadastro configurado']]){
const url=document.getElementById(id).value.trim();
try{const u=new URL(url);if(u.protocol!=='https:')continue;
const a=document.createElement('a');a.href=u.href;a.target='_blank';a.rel='noopener';
a.textContent=label;target.append(a,document.createTextNode('  '));}catch(e){}
}});</script></main></html>"""
