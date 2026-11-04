import os
import time
import hmac
import hashlib
import base64
import secrets
import html
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, Form
from pydantic import BaseModel, Field
from consultor import answer as consultor_answer
from knowledge import read_knowledge, save_knowledge
from integrations import router as meta_router, integration_status
from meta_ads import router as ads_router
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

app = FastAPI(title="Z1 Prospect IA")
app.include_router(meta_router)
app.include_router(ads_router)
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
    if req.url.path in ("/healthz", "/login", "/webhooks/meta"):
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
    form = parse_qs((await req.body()).decode("utf-8", errors="replace"))
    entered_user = form.get("username", [""])[0]
    entered_password = form.get("password", [""])[0]
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
<p><a href="/consultor">Abrir consultor de IA</a> · <a href="/ensinar">Ensinar a IA</a> · <a href="/integracoes">Integrações</a> · <a href="/meta-ads">Meta Ads</a> · <a href="/logout">Sair da conta</a></p>
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

class ChatMessage(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=2000)

class ChatInput(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)

@app.post("/api/chat")
async def chat(payload: ChatInput):
    messages = [{"role": item.role, "content": item.content} for item in payload.messages
                if item.role in ("user", "assistant")]
    if not messages or messages[-1]["role"] != "user":
        return JSONResponse({"error": "Envie uma pergunta."}, status_code=400)
    return await consultor_answer(messages)

@app.get("/consultor", response_class=HTMLResponse)
def consultor_page():
    return """<!doctype html><html lang="pt-br"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Consultor — Z1 Prospect IA</title>
<style>body{background:#111;color:#eee;font:16px system-ui;margin:0;padding:20px}
main{max-width:720px;margin:auto}a{color:#e6b95b}
#conversation{background:#222;border-radius:12px;padding:16px;min-height:260px;max-height:55vh;overflow:auto}
.message{white-space:pre-wrap;margin:12px 0;padding:12px;border-radius:10px;background:#333}
.mine{background:#3c321e}textarea{box-sizing:border-box;width:100%;min-height:90px;
margin:16px 0 8px;background:#222;color:#fff;border:1px solid #777;border-radius:8px;
padding:12px;font:inherit}button{padding:12px 22px;background:#e6b95b;color:#111;
border:0;border-radius:8px;font-weight:bold}small{color:#bbb}</style>
<main><p><a href="/">← Painel</a></p><h1>✨ Consultor Z1</h1>
<p>Teste administrativo de respostas sobre produtos e oportunidade Zyone.</p>
<div id="conversation" aria-live="polite"><div class="message">Olá! Faça uma pergunta sobre o catálogo, a oportunidade ou o cadastro.</div></div>
<textarea id="question" maxlength="2000" placeholder="Digite sua pergunta..."></textarea>
<button id="send">Enviar pergunta</button>
<p id="status" role="status"></p><small>Não compartilhe dados pessoais ou senhas.
O conteúdo do catálogo ainda não foi importado. O histórico fica apenas nesta tela.</small>
<script>
const history=[];
const box=document.getElementById('conversation');
const question=document.getElementById('question');
const button=document.getElementById('send');
const status=document.getElementById('status');
function add(text,mine){const div=document.createElement('div');
div.className='message'+(mine?' mine':'');div.textContent=text;box.appendChild(div);
box.scrollTop=box.scrollHeight;}
button.addEventListener('click',async()=>{
const text=question.value.trim();if(!text||button.disabled)return;
question.value='';add(text,true);history.push({role:'user',content:text});
button.disabled=true;status.textContent='Consultando...';
try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({messages:history.slice(-12)})});
if(!r.ok)throw new Error('HTTP '+r.status);
const data=await r.json();add(data.answer||'Resposta não disponível.',false);
history.push({role:'assistant',content:data.answer||''});
}catch(e){add('Falha de conexão. Confira o login e tente novamente.',false);
history.pop();}finally{button.disabled=false;status.textContent='';}
});
</script></main></html>"""

class KnowledgeInput(BaseModel):
    content: str = Field(max_length=20000)

@app.get("/api/knowledge")
def knowledge_get():
    return {"content": read_knowledge()}

@app.post("/api/knowledge")
def knowledge_save(payload: KnowledgeInput):
    save_knowledge(payload.content)
    return {"saved": True}

@app.get("/ensinar", response_class=HTMLResponse)
def knowledge_editor():
    value = html.escape(read_knowledge())
    return """<!doctype html><html lang="pt-br"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ensinar IA — Z1</title><style>
body{background:#111;color:#eee;font:16px system-ui;padding:20px}
a{color:#e6b95b}main{max-width:750px;margin:auto}
textarea{box-sizing:border-box;width:100%;height:50vh;background:#222;color:white;
border:1px solid #888;border-radius:10px;padding:12px;font:16px system-ui}
button{background:#e6b95b;padding:14px;border:0;border-radius:8px;font-weight:bold}
</style><main><p><a href="/">Painel</a> · <a href="/consultor">Testar IA</a></p>
<h1>Ensinar a IA</h1><p>Adicione informações verificadas sobre produtos, preços, regras e dúvidas frequentes.</p>
<textarea id="data" maxlength="20000">""" + value + """</textarea>
<p><button id="save">Salvar informações</button></p><p id="status"></p>
<p>Não insira dados pessoais ou senhas. Sem armazenamento persistente no Render,
o conteúdo pode ser perdido em reinícios ou deploys. Guarde uma cópia.</p>
<script>
document.getElementById('save').onclick=async function(){
const s=document.getElementById('status');s.textContent='Salvando...';
try{const r=await fetch('/api/knowledge',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({content:document.getElementById('data').value})});
if(!r.ok)throw Error(r.status);s.textContent='Salvo! Teste no consultor.';
}catch(e){s.textContent='Erro ao salvar: '+e.message;}
};</script></main></html>"""

@app.get("/api/integrations")
def integrations_status():
    return integration_status()

@app.get("/integracoes", response_class=HTMLResponse)
def integrations_page():
    s = integration_status()
    def state(key):
        return "Configurado" if s[key] else "Pendente"
    return """<!doctype html><html lang="pt-br"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Integrações — Z1</title>
<style>body{font:16px system-ui;background:#111;color:#eee;padding:20px}
main{max-width:740px;margin:auto}section{background:#222;border-radius:12px;padding:16px;margin:14px 0}
a{color:#e6b95b}code{overflow-wrap:anywhere;color:#ffcf72}</style>
<main><p><a href="/">← Painel</a></p><h1>Integrações oficiais</h1>
<section><h2>Meta Ads</h2><p>Prepare rascunhos, revise e crie campanhas pausadas.</p>
<p><a href="/meta-ads">Abrir campanhas Meta Ads</a></p></section>
<section><h2>Meta Webhook</h2><p>""" + state("meta_webhook") + """</p>
<p>URL para configuração no painel Meta Developers:</p>
<code>https://z1-prospect-ia.onrender.com/webhooks/meta</code>
<p>Variáveis no Render: META_APP_SECRET e META_VERIFY_TOKEN.</p></section>
<section><h2>WhatsApp Business Cloud API</h2><p>""" + state("whatsapp") + """</p>
<p>Adicione WHATSAPP_ACCESS_TOKEN e WHATSAPP_PHONE_NUMBER_ID.
Para habilitar respostas automáticas após aprovação e testes, configure
Z1_WHATSAPP_AUTO_REPLY=true. Inicialmente está desabilitado.</p></section>
<section><h2>Instagram</h2><p>""" + state("instagram") + """</p>
<p>O webhook recebe eventos assinados, mas a troca de mensagens ainda depende de
permissões e tokens oficiais do Instagram. Não há prospecção não solicitada.</p></section>
<section><h2>Cadastro Zyone</h2><p>Link disponível. Integração de cadastro via API
depende de documentação e credenciais oficiais da Zyone.</p></section>
</main></html>"""

