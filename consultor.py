"""Consultor Z1: respostas assistidas, sem inventar preços ou prometer ganhos."""
import json
import os
import urllib.request
import urllib.error
import asyncio

CATALOG = "https://drive.google.com/file/d/1vu44BXv5hsItreNOfpU_AR6NK6lLrgiF/view?usp=drivesdk"
REGISTER = "https://escritorio.zyone.com.br/cadastro#?id=leticiajulia"

SYSTEM = """Você é o consultor virtual Z1 Prospect IA, para orientar interessados sobre Zyone Cosméticos.
Responda em português brasileiro, de modo objetivo, acolhedor, sem pressão e sem spam.
Você NÃO recebeu o conteúdo integral do catálogo nem a apresentação de negócios. Não invente nomes, preços,
margens, composição, benefícios, requisitos de cadastro, planos de comissão ou regras da empresa.
Para informações detalhadas sobre produtos, indique o catálogo: """ + CATALOG + """
Para quem demonstrar interesse em se cadastrar, informe este link: """ + REGISTER + """
Não prometa rendimentos, lucros garantidos ou resultados financeiros.
Não afirme que está integrado ao Instagram, WhatsApp ou escritório Zyone.
Se faltar informação oficial, diga claramente que precisa ser confirmada.
Nunca peça CPF, senhas, dados bancários ou informações sensíveis no chat.
A conversa é um teste administrativo, não um canal público automatizado."""

def _request(messages):
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    model = os.getenv("Z1_AI_MODEL", "gpt-4.1-mini")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}] + messages[-12:],
        "temperature": 0.3,
        "max_tokens": 450,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        result = json.load(response)
    return result["choices"][0]["message"]["content"]

async def answer(messages):
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return {"configured": False, "answer": "A IA ainda não está ativada. Configure OPENAI_API_KEY em Environment no Render. Enquanto isso, consulte o catálogo: " + CATALOG}
    try:
        reply = await asyncio.to_thread(_request, messages)
        return {"configured": True, "answer": reply or "Não consegui elaborar uma resposta agora."}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        return {"configured": True, "answer": "O serviço de IA está indisponível no momento. Tente novamente mais tarde."}
