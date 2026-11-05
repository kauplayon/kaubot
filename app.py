import os
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


@app.after_request
def disable_page_cache(response):
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Digite uma mensagem para conversar."}), 400
    if len(message) > 4000:
        return jsonify({"error": "A mensagem passou do limite de 4.000 caracteres."}), 400

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return jsonify({"error": "IA ainda não configurada no servidor."}), 503

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        history = payload.get("history", [])
        contents = []
        if isinstance(history, list):
            for item in history[-10:]:
                if not isinstance(item, dict):
                    continue
                role = "user" if item.get("role") == "user" else "model"
                text = str(item.get("text", ""))[:4000]
                if text:
                    contents.append({"role": role, "parts": [{"text": text}]})
        contents.append({"role": "user", "parts": [{"text": message}]})
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        result = client.models.generate_content(
            model=model,
            contents=contents,
            config={"system_instruction": "Você é o NEXUS, um assistente útil, seguro e objetivo. Responda em português do Brasil."},
        )
        reply = (getattr(result, "text", None) or "").strip()
        if not reply:
            return jsonify({"error": "A IA não retornou uma resposta. Tente novamente."}), 502
        return jsonify({"reply": reply})
    except Exception:
        app.logger.exception("Falha ao consultar o provedor de IA")
        return jsonify({"error": "O serviço de IA está temporariamente indisponível."}), 502


@app.get("/health")
def health():
    return jsonify({
        "status": "online",
        "application": "NEXUS",
        "version": "1.1.0",
        "ai_configured": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
