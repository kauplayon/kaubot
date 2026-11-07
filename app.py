import json
import os
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

SYSTEM_PROMPT = """Você é o NEXUS, o assistente inteligente da Central de Comando.
Fale em português do Brasil, com clareza, cordialidade e objetividade.
Ajude com estudos, programação, organização, tecnologia e tarefas do dia a dia.
Use o contexto recente da conversa quando ele for fornecido. Não invente ações:
você não controla o computador nem executa ações externas por conta própria.
Quando sugerir uma ação dentro do NEXUS, diga claramente qual módulo o usuário
pode abrir. Organize respostas com listas curtas quando isso ajudar."""


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


def _history_messages(history):
    messages = []
    if not isinstance(history, list):
        return messages
    for item in history[-12:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role not in ("user", "assistant", "model"):
            continue
        content = str(item.get("text", "")).strip()[:4000]
        if content:
            messages.append({
                "role": "assistant" if role == "model" else role,
                "content": content,
            })
    return messages


def _cloudflare_chat(messages):
    token = (
        os.getenv("CLOUDFLARE_API_TOKEN")
        or os.getenv("CF_API_TOKEN")
        or os.getenv("CLOUDFLARE_API_KEY")
    )
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID")
    if not token or not account_id:
        return None

    model = os.getenv("CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + account_id
        + "/ai/v1/chat/completions"
    )
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": 0.65,
        "max_tokens": 1200,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))
    choices = result.get("choices") or []
    if not choices:
        raise RuntimeError("Cloudflare não retornou escolhas de resposta.")
    reply = (choices[0].get("message") or {}).get("content", "")
    if isinstance(reply, list):
        reply = "".join(
            part.get("text", "") for part in reply if isinstance(part, dict)
        )
    return str(reply).strip()


def _gemini_chat(messages):
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    from google import genai

    client = genai.Client(api_key=api_key)
    contents = []
    for item in messages:
        contents.append({
            "role": "user" if item["role"] == "user" else "model",
            "parts": [{"text": item["content"]}],
        })
    result = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=contents,
        config={"system_instruction": SYSTEM_PROMPT},
    )
    return (getattr(result, "text", None) or "").strip()


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Digite uma mensagem para conversar."}), 400
    if len(message) > 4000:
        return jsonify({"error": "A mensagem passou do limite de 4.000 caracteres."}), 400

    messages = _history_messages(payload.get("history"))
    messages.append({"role": "user", "content": message})
    cloudflare_ready = bool(
        (os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN") or os.getenv("CLOUDFLARE_API_KEY"))
        and (os.getenv("CLOUDFLARE_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID"))
    )
    gemini_ready = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    if not cloudflare_ready and not gemini_ready:
        return jsonify({
            "error": "IA não configurada: confira se o token e o Account ID da Cloudflare estão nas variáveis do Render."
        }), 503

    try:
        if cloudflare_ready:
            reply = _cloudflare_chat(messages)
            provider = "cloudflare"
        else:
            reply = _gemini_chat(messages)
            provider = "gemini"
        if not reply:
            return jsonify({"error": "A IA não retornou uma resposta. Tente novamente."}), 502
        return jsonify({"reply": reply, "provider": provider})
    except urllib.error.HTTPError as exc:
        app.logger.error("Cloudflare AI retornou HTTP %s", exc.code)
        if gemini_ready and cloudflare_ready:
            try:
                reply = _gemini_chat(messages)
                if reply:
                    return jsonify({"reply": reply, "provider": "gemini"})
            except Exception:
                app.logger.exception("Fallback Gemini também falhou")
        return jsonify({"error": "A Cloudflare recusou a solicitação. Confira as permissões do token, o Account ID, os créditos e o modelo configurado."}), 502
    except Exception:
        app.logger.exception("Falha ao consultar o provedor de IA")
        return jsonify({"error": "O serviço de IA está temporariamente indisponível. Tente novamente em instantes."}), 502


@app.get("/health")
def health():
    cloudflare_ready = bool(
        (os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN") or os.getenv("CLOUDFLARE_API_KEY"))
        and (os.getenv("CLOUDFLARE_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID"))
    )
    gemini_ready = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return jsonify({
        "status": "online",
        "application": "NEXUS",
        "version": "2.0.0",
        "ai_configured": cloudflare_ready or gemini_ready,
        "ai_provider": "cloudflare" if cloudflare_ready else ("gemini" if gemini_ready else "not_configured"),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
