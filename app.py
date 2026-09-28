import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

load_dotenv()
app = Flask(__name__)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) if os.getenv("GEMINI_API_KEY") else None

SYSTEM = """Você é KauBot, um chatbot amigável criado por Kauplayon.
Responda em português do Brasil, de forma clara, correta e educada.
Se não souber algo, diga que não sabe. Explique assuntos difíceis de forma simples.
Considere o contexto recente da conversa."""

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    if not messages:
        return jsonify({"reply":"Envie uma pergunta para começarmos."})
    if client:
        try:
            contents = []
            for item in messages[-12:]:
                role = "user" if item.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": str(item.get("content",""))[:4000]}]})
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config={"system_instruction": SYSTEM, "temperature": 0.7}
            )
            return jsonify({"reply": response.text or "Não consegui formular uma resposta."})
        except Exception:
            app.logger.exception("Erro na API Gemini")
            return jsonify({"reply":"Não consegui acessar a IA agora. Confira a chave e tente novamente."}), 502
    return jsonify({"reply": local_reply(messages[-1].get("content",""))})

def local_reply(text):
    """Fallback simples, baseado em regras; não é um modelo generativo."""
    t = text.lower().strip()
    if any(x in t for x in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return "Olá! Eu sou o KauBot. Como posso ajudar?"
    if "seu nome" in t:
        return "Sou o KauBot, criado no projeto de Kauplayon."
    if "ajuda" in t:
        return "Posso conversar e responder perguntas quando a API Gemini estiver configurada. Sem ela, funciono apenas com respostas simples."
    return "Ainda estou no modo básico. Configure uma chave da API Gemini no arquivo .env para eu responder perguntas variadas."

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
