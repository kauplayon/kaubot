import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

api_token = os.getenv("CLOUDFLARE_API_TOKEN")
account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
client_configured = bool(api_token and account_id)

BOT_NAME = os.getenv("BOT_NAME", "Cosmo")
BOT_PERSONALITY = os.getenv(
    "BOT_PERSONALITY",
    "Amigável, paciente, curioso e didático. Use linguagem simples e natural."
)
SYSTEM = f"""Você é {BOT_NAME}, um assistente virtual criado por Kauplayon.
Sua personalidade: {BOT_PERSONALITY}
Responda em português do Brasil, de forma clara, correta e educada.
Você pode responder perguntas gerais e também explicar como funciona o próprio bot.
Se não souber algo ou não tiver certeza, diga isso claramente; não invente fatos.
Explique assuntos difíceis de forma simples e considere o contexto recente da conversa.
Não peça nem revele senhas, chaves de API ou outros dados secretos."""

@app.get("/")
def index():
    return render_template("index.html", bot_name=BOT_NAME)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "ai_configured": client_configured})

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify({"reply": "Envie uma pergunta para começarmos."}), 400

    conversation = [{"role": "system", "content": SYSTEM}]
    for item in messages[-12:]:
        if not isinstance(item, dict):
            continue
        role = "user" if item.get("role") == "user" else "assistant"
        content = str(item.get("content", ""))[:4000]
        if content.strip():
            conversation.append({"role": role, "content": content})

    if len(conversation) == 1:
        return jsonify({"reply": "Não encontrei uma mensagem válida."}), 400

    if client_configured:
        try:
            model = os.getenv(
                "CLOUDFLARE_MODEL",
                "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
            )
            url = (
                f"https://api.cloudflare.com/client/v4/accounts/"
                f"{account_id}/ai/run/{model}"
            )
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_token}"},
                json={"messages": conversation},
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            reply = (result.get("result") or {}).get("response")
            if not reply:
                raise ValueError("A Cloudflare não retornou uma resposta.")
            return jsonify({"reply": reply})
        except Exception:
            app.logger.exception("Erro na API Cloudflare Workers AI")
            return jsonify({
                "reply": "Não consegui acessar a IA agora. Verifique a configuração da Cloudflare e tente novamente."
            }), 502

    return jsonify({"reply": local_reply(conversation[-1]["content"])})

def local_reply(text):
    """Fallback simples, baseado em regras; não é um modelo generativo."""
    t = text.lower().strip()
    if any(x in t for x in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return f"Olá! Eu sou {BOT_NAME}. Como posso ajudar?"
    if "seu nome" in t or "quem é você" in t or "quem e voce" in t:
        return f"Sou o {BOT_NAME}, criado por Kauplayon."
    if "api" in t or "como você funciona" in t or "como voce funciona" in t:
        return "Quando a API Cloudflare Workers AI está configurada, uso um modelo de IA hospedado pela Cloudflare para responder. Sem as credenciais, só consigo dar respostas básicas."
    return "A IA ainda não está configurada. O administrador precisa adicionar CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID nas configurações do servidor."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
