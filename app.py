import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

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
    return jsonify({"status": "ok", "ai_configured": client is not None})

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify({"reply": "Envie uma pergunta para começarmos."}), 400

    contents = []
    for item in messages[-12:]:
        if not isinstance(item, dict):
            continue
        role = "user" if item.get("role") == "user" else "model"
        content = str(item.get("content", ""))[:4000]
        if content.strip():
            contents.append({"role": role, "parts": [{"text": content}]})
    if not contents:
        return jsonify({"reply": "Não encontrei uma mensagem válida."}), 400

    if client:
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=contents,
                config={"system_instruction": SYSTEM, "temperature": 0.7}
            )
            return jsonify({"reply": response.text or "Não consegui formular uma resposta."})
        except Exception:
            app.logger.exception("Erro na API Gemini")
            return jsonify({"reply": "Não consegui acessar a IA agora. Confira a configuração da API e tente novamente."}), 502

    return jsonify({"reply": local_reply(contents[-1]["parts"][0]["text"])})

def local_reply(text):
    """Fallback simples, baseado em regras; não é um modelo generativo."""
    t = text.lower().strip()
    if any(x in t for x in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return f"Olá! Eu sou {BOT_NAME}. Como posso ajudar?"
    if "seu nome" in t or "quem é você" in t or "quem e voce" in t:
        return f"Sou o {BOT_NAME}, criado por Kauplayon."
    if "api" in t or "como você funciona" in t or "como voce funciona" in t:
        return "Quando a API Gemini está configurada, uso um modelo de IA hospedado pelo Google para responder. Sem a chave, só consigo dar respostas básicas."
    return "A IA ainda não está configurada. O administrador precisa adicionar a variável GEMINI_API_KEY nas configurações do servidor."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
