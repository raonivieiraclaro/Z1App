import os, secrets, base64
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
app=FastAPI(title="Z1 Prospect IA")
CATALOG="https://drive.google.com/file/d/1vu44BXv5hsItreNOfpU_AR6NK6lLrgiF/view?usp=drivesdk"
REGISTER="https://escritorio.zyone.com.br/cadastro#?id=leticiajulia"
@app.middleware("http")
async def auth(req:Request,call_next):
 if req.url.path=="/healthz": return await call_next(req)
 u=os.getenv("Z1_ADMIN_USER",""); p=os.getenv("Z1_ADMIN_PASSWORD","")
 if not u or not p:return JSONResponse({"error":"Configure as credenciais no Render"},status_code=503)
 try:
  scheme,token=req.headers.get("authorization","").split(" ",1)
  candidate=base64.b64decode(token,validate=True).decode().split(":",1) if scheme.lower()=="basic" else ["",""]
 except Exception:candidate=["",""]
 if len(candidate)!=2 or not (secrets.compare_digest(candidate[0],u) and secrets.compare_digest(candidate[1],p)):
  return JSONResponse({"error":"Autenticação necessária"},status_code=401,headers={"WWW-Authenticate":'Basic realm="Z1 Prospect IA"'})
 return await call_next(req)
@app.get("/healthz")
def health():return {"status":"ok"}
@app.get("/",response_class=HTMLResponse)
def home():
 return """<!doctype html><html lang="pt-br"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>Z1 Prospect IA</title><style>body{font-family:system-ui;background:#111;color:#eee;margin:0;padding:24px}main{max-width:680px;margin:auto}section{background:#222;padding:20px;border-radius:12px;margin:16px 0}a{color:#e6b95b}input{width:95%;padding:10px;margin:6px 0;background:#333;color:white;border:1px solid #777;border-radius:6px}button{padding:12px;background:#e6b95b;border:0;border-radius:6px}</style><main><h1>✨ Z1 Prospect IA</h1><p>Painel de demonstração — Zyone Cosméticos</p><section><h2>Catálogo</h2><a href='""" + CATALOG + """' target="_blank" rel="noopener">Abrir catálogo Zyone</a></section><section><h2>Link de cadastro</h2><a href='""" + REGISTER + """' target="_blank" rel="noopener">Abrir cadastro</a></section><section><h2>Configurações locais de links</h2><p>Estes campos são apenas para testes nesta sessão; não persistem no servidor.</p><label>Catálogo</label><input id="catalog" value='""" + CATALOG + """'><label>Cadastro</label><input id="register" value='""" + REGISTER + """'><button onclick="document.getElementById('links').innerHTML='<a target=_blank rel=noopener href='+encodeURI(document.getElementById('catalog').value)+'>Catálogo configurado</a> | <a target=_blank rel=noopener href='+encodeURI(document.getElementById('register').value)+'>Cadastro configurado</a>'">Aplicar nesta tela</button><p id="links"></p></section><section><h2>Integrações</h2><p>Instagram, WhatsApp e escritório Zyone: ainda não conectados. Não insira tokens neste protótipo.</p></section></main></html>"""
