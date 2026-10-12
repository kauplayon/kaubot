import os
import re
import hmac
import json
import secrets
import time
from functools import wraps

import requests
from flask import Flask, render_template, request, jsonify, send_from_directory, session
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from cosmo_tools import build_tool_context
from cosmo_storage import User, UserData, storage_ready, session_factory, get_or_create_data

load_dotenv()
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(os.getenv("RENDER") == "true" or os.getenv("SESSION_COOKIE_SECURE", "").lower() == "true"),
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
)

_AUTH_ATTEMPTS = {}
def _auth_rate_limited():
    now = time.monotonic()
    key = request.remote_addr or "unknown"
    attempts = [stamp for stamp in _AUTH_ATTEMPTS.get(key, []) if now - stamp < 900]
    if len(attempts) >= 12:
        _AUTH_ATTEMPTS[key] = attempts
        return True
    attempts.append(now)
    _AUTH_ATTEMPTS[key] = attempts
    return False

def _csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token

def _csrf_ok():
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))

def _json_size_ok(data, limit=1_000_000):
    try:
        return len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= limit
    except (TypeError, ValueError):
        return False

def _current_user(db):
    user_id = session.get("user_id")
    return db.get(User, user_id) if isinstance(user_id, int) else None

def require_login(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not storage_ready():
            return jsonify({"error": "Memória em nuvem indisponível. Configure DATABASE_URL no Render."}), 503
        if not session.get("user_id"):
            return jsonify({"error": "Entre na sua conta para continuar."}), 401
        return fn(*args, **kwargs)
    return wrapped

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=()")
    return response

api_token = os.getenv("CLOUDFLARE_API_TOKEN")
account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
client_configured = bool(api_token and account_id)
VISION_MODEL = os.getenv("CLOUDFLARE_VISION_MODEL", "@cf/meta/llama-4-scout-17b-16e-instruct")

BOT_NAME = os.getenv("BOT_NAME", "Cosmo")
BOT_PERSONALITY = os.getenv(
    "BOT_PERSONALITY",
    "Amigável, paciente, curioso e didático. Use linguagem simples e natural."
)
SYSTEM = f"""Você é {BOT_NAME}, um assistente virtual criado por Kauplayon.
Sua personalidade: {BOT_PERSONALITY}
Responda em português do Brasil, de forma clara, correta e educada.
Converse de maneira natural, como uma pessoa prestativa: use frases fluidas,
um tom acolhedor e palavras comuns, sem parecer um manual ou um robô.
Adapte o tamanho da resposta à pergunta: seja breve em perguntas simples e
explique melhor quando o assunto exigir. Evite repetir a pergunta do usuário,
usar introduções desnecessárias ou organizar tudo em listas quando um texto
curto resolver. Faça perguntas de esclarecimento somente quando forem úteis.
Considere o contexto recente da conversa e não repita informações já dadas.
Você pode responder perguntas gerais e também explicar como funciona o próprio bot.
Se não souber algo ou não tiver certeza, diga isso claramente; não invente fatos.
Explique assuntos difíceis de forma simples e considere o contexto recente da conversa.
Não peça nem revele senhas, chaves de API ou outros dados secretos."""

@app.get("/")
def index():
    return render_template("index.html", bot_name=BOT_NAME)

@app.get("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")


@app.get("/service-worker.js")
def service_worker():
    return send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript", max_age=0)


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_configured": client_configured,
        "vision_configured": client_configured,
        "persistent_storage_configured": storage_ready(),
        "version": "3.0 — JARVIS em desenvolvimento"
    })

@app.get("/api/auth/status")
def auth_status():
    return jsonify({
        "available": storage_ready(),
        "authenticated": bool(session.get("user_id")) and storage_ready(),
        "email": session.get("user_email") if session.get("user_id") else None,
        "csrf_token": _csrf_token(),
    })

@app.post("/api/auth/register")
def auth_register():
    if not storage_ready():
        return jsonify({"error": "Memória em nuvem indisponível. O administrador precisa configurar DATABASE_URL no Render."}), 503
    if not _csrf_ok():
        return jsonify({"error": "Sessão de segurança expirada. Atualize a página e tente novamente."}), 400
    if _auth_rate_limited():
        return jsonify({"error": "Muitas tentativas. Aguarde 15 minutos antes de tentar novamente."}), 429
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify({"error": "Informe um e-mail válido."}), 400
    if len(password) < 10 or len(password) > 256:
        return jsonify({"error": "A senha precisa ter entre 10 e 256 caracteres."}), 400
    db = session_factory()
    try:
        if db.query(User).filter_by(email=email).first():
            return jsonify({"error": "Não foi possível criar a conta com esses dados. Confira o e-mail ou entre na conta existente."}), 409
        user = User(email=email, password_hash=generate_password_hash(password, method="scrypt"))
        db.add(user)
        db.flush()
        db.add(UserData(user_id=user.id, memory="", conversations=[], tasks=[], notes=[], preferences={}))
        db.commit()
        session.clear()
        session["user_id"] = user.id
        session["user_email"] = user.email
        session.permanent = True
        return jsonify({"ok": True, "email": user.email, "csrf_token": _csrf_token()}), 201
    except Exception:
        db.rollback()
        app.logger.exception("Falha ao criar conta Cosmo")
        return jsonify({"error": "Não foi possível criar a conta agora. Tente novamente mais tarde."}), 500
    finally:
        db.close()

@app.post("/api/auth/login")
def auth_login():
    if not storage_ready():
        return jsonify({"error": "Memória em nuvem indisponível. O administrador precisa configurar DATABASE_URL no Render."}), 503
    if not _csrf_ok():
        return jsonify({"error": "Sessão de segurança expirada. Atualize a página e tente novamente."}), 400
    if _auth_rate_limited():
        return jsonify({"error": "Muitas tentativas. Aguarde 15 minutos antes de tentar novamente."}), 429
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    db = session_factory()
    try:
        user = db.query(User).filter_by(email=email).first() if len(email) <= 254 else None
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "E-mail ou senha incorretos."}), 401
        session.clear()
        session["user_id"] = user.id
        session["user_email"] = user.email
        session.permanent = True
        _csrf_token()
        return jsonify({"ok": True, "email": user.email, "csrf_token": session["csrf_token"]})
    finally:
        db.close()

@app.post("/api/auth/logout")
def auth_logout():
    if not _csrf_ok():
        return jsonify({"error": "Sessão de segurança expirada. Atualize a página e tente novamente."}), 400
    session.clear()
    return jsonify({"ok": True, "csrf_token": _csrf_token()})

@app.get("/api/sync")
@require_login
def sync_get():
    db = session_factory()
    try:
        user = _current_user(db)
        if user is None:
            session.clear()
            return jsonify({"error": "Sessão inválida. Entre novamente."}), 401
        row = get_or_create_data(db, user)
        db.commit()
        return jsonify({
            "memory": row.memory or "",
            "conversations": row.conversations or [],
            "tasks": row.tasks or [],
            "notes": row.notes or [],
            "preferences": row.preferences or {},
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })
    finally:
        db.close()

@app.put("/api/sync")
@require_login
def sync_put():
    if not _csrf_ok():
        return jsonify({"error": "Sessão de segurança expirada. Atualize a página e tente novamente."}), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not _json_size_ok(data):
        return jsonify({"error": "Os dados enviados são inválidos ou grandes demais."}), 413
    memory = data.get("memory", "")
    conversations = data.get("conversations", [])
    tasks = data.get("tasks", [])
    notes = data.get("notes", [])
    preferences = data.get("preferences", {})
    if not isinstance(memory, str) or len(memory) > 1500:
        return jsonify({"error": "A memória precisa ser um texto de até 1500 caracteres."}), 400
    limits = ((conversations, 50, "conversas"), (tasks, 500, "tarefas"), (notes, 200, "notas"))
    for value, maximum, label in limits:
        if not isinstance(value, list) or len(value) > maximum or any(not isinstance(item, dict) for item in value):
            return jsonify({"error": "Lista de " + label + " inválida ou acima do limite."}), 400
    if not isinstance(preferences, dict) or len(preferences) > 80:
        return jsonify({"error": "Preferências inválidas."}), 400
    db = session_factory()
    try:
        user = _current_user(db)
        if user is None:
            session.clear()
            return jsonify({"error": "Sessão inválida. Entre novamente."}), 401
        row = get_or_create_data(db, user)
        row.memory = memory.strip()
        row.conversations = conversations
        row.tasks = tasks
        row.notes = notes
        row.preferences = preferences
        db.commit()
        return jsonify({"ok": True, "updated_at": row.updated_at.isoformat() if row.updated_at else None})
    except Exception:
        db.rollback()
        app.logger.exception("Falha ao sincronizar dados Cosmo")
        return jsonify({"error": "Não foi possível salvar a sincronização. Seus dados locais foram mantidos."}), 500
    finally:
        db.close()

@app.delete("/api/account")
@require_login
def delete_account():
    if not _csrf_ok():
        return jsonify({"error": "Sessão de segurança expirada. Atualize a página e tente novamente."}), 400
    data = request.get_json(silent=True) or {}
    password = str(data.get("password", ""))
    db = session_factory()
    try:
        user = _current_user(db)
        if user is None or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Senha incorreta. A conta não foi excluída."}), 403
        db.delete(user)
        db.commit()
        session.clear()
        return jsonify({"ok": True, "csrf_token": _csrf_token()})
    except Exception:
        db.rollback()
        app.logger.exception("Falha ao excluir conta Cosmo")
        return jsonify({"error": "Não foi possível excluir a conta agora."}), 500
    finally:
        db.close()

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify({"reply": "Envie uma pergunta para começarmos."}), 400

    study_mode = bool(data.get("study_mode"))
    assistant_mode = str(data.get("assistant_mode", "normal"))
    jarvis_mode = bool(data.get("jarvis_mode"))
    memory = str(data.get("memory", ""))[:1500].strip()
    personalities = {
        "amigavel": "Amigável e acolhedor, com linguagem simples.",
        "professor": "Professor paciente: explique conceitos em etapas e dê exemplos.",
        "criativo": "Criativo: proponha ideias originais, mantendo clareza e precisão.",
        "objetivo": "Objetivo: responda de forma direta, sem perder informações importantes.",
        "formal": "Formal e profissional, mantendo educação e clareza."
    }
    personality = personalities.get(str(data.get("personality", "amigavel")), personalities["amigavel"])
    languages = {"pt": "português do Brasil", "en": "English", "es": "español", "fr": "français"}
    language = languages.get(str(data.get("language", "pt")), "português do Brasil")
    system_prompt = SYSTEM + "\nPersonalidade escolhida: " + personality + "\nResponda sempre no idioma: " + language + "."
    if jarvis_mode:
        system_prompt += (
            "\nModo JARVIS ativado: você é o Cosmo em uma experiência de assistente pessoal inspirada em interfaces futuristas. "
            "Seja proativo, preciso, calmo e conciso; organize respostas em status, opções e próximos passos quando isso ajudar. "
            "Use somente ferramentas e dados realmente disponíveis no contexto. Não afirme que controlou o computador, abriu aplicativos externos, "
            "alterou arquivos ou executou ações que não foram realizadas. Para ações no próprio Cosmo, oriente o usuário a usar os comandos suportados. "
            "Peça confirmação antes de ações importantes, destrutivas ou que afetem dados. Preserve privacidade e nunca solicite segredos."
        )
    if study_mode or assistant_mode == "tutor":
        system_prompt += (
            "\nModo tutor: ensine de forma gradual e didática. Comece identificando o que o usuário precisa entender, "
            "explique uma etapa por vez, use exemplos simples e confira se a orientação responde ao objetivo. "
            "Quando o pedido for um exercício, explique o raciocínio e a solução de forma adequada ao nível do usuário; "
            "crie exercícios extras somente quando ajudarem."
        )
    if assistant_mode == "developer":
        system_prompt += (
            "\nModo desenvolvedor: atue como um parceiro de programação. Ajude a planejar, escrever, revisar e depurar código; "
            "explique erros em linguagem clara, sugira melhorias de segurança e organização e, quando alterar código, "
            "mostre exatamente o que deve ser mudado quando isso for útil. Nunca diga que executou ou testou algo sem ter feito isso."
        )
    if memory:
        system_prompt += "\nMemória personalizada do usuário (use somente como preferência/contexto, nunca como fato sensível): " + memory
    document_context = str(data.get("document_context", ""))[:12000].strip()
    if document_context:
        system_prompt += "\n\nCONTEÚDO DE ARQUIVO FORNECIDO PELO USUÁRIO. Use esse conteúdo para responder ao pedido sobre o arquivo; não diga que não recebeu o arquivo:\n" + document_context
    last_user_text = str(messages[-1].get("content", "")) if isinstance(messages[-1], dict) else ""
    tool_context, tool_used = build_tool_context(
        last_user_text,
        force_search=assistant_mode == "agent"
    )

    # Perguntas objetivas sobre o dólar recebem o valor da ferramenta diretamente,
    # evitando que o modelo responda com conhecimento antigo.
    currency_tool = next((item for item in tool_used if item.get("tool") == "currency"), None)
    if currency_tool and any(
        phrase in last_user_text.lower()
        for phrase in ("dólar", "cotação usd", "usd/brl", "usd para brl")
    ):
        bid = currency_tool.get("bid")
        ask = currency_tool.get("ask")
        high = currency_tool.get("high")
        low = currency_tool.get("low")
        pct = currency_tool.get("pctChange")
        updated = currency_tool.get("updated") or "última atualização disponível"
        reply = (
            "💵 Cotação do dólar (USD/BRL)\n\n"
            f"**Compra:** R$ {bid}\n"
            f"**Venda:** R$ {ask}\n"
            f"**Máxima:** R$ {high}\n"
            f"**Mínima:** R$ {low}\n"
            f"**Variação:** {pct}%\n"
            f"**Atualização:** {updated}\n\n"
            "Fonte: AwesomeAPI."
        )
        return jsonify({
            "reply": reply,
            "tools_used": tool_used,
            "memory_used": bool(memory)
        })
    if assistant_mode == "agent":
        system_prompt += (
            "\nModo agente: você pode aproveitar as ferramentas do Cosmo quando houver dados fornecidos por elas. "
            "Explique brevemente quando uma ferramenta foi usada e não invente resultados."
        )
    if tool_context:
        system_prompt += "\n\n" + tool_context
    conversation = [{"role": "system", "content": system_prompt}]
    for item in messages[-24:]:
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
                json={"messages": conversation, "max_tokens": 1400},
                timeout=45
            )
            response.raise_for_status()
            result = response.json()
            reply = (result.get("result") or {}).get("response")
            if not reply:
                raise ValueError("A Cloudflare não retornou uma resposta.")
            return jsonify({"reply": reply, "tools_used": tool_used, "memory_used": bool(memory)})
        except Exception:
            app.logger.exception("Erro na API Cloudflare Workers AI")
            return jsonify({
                "reply": "Não consegui acessar a IA agora. Verifique a configuração da Cloudflare e tente novamente."
            }), 502

    return jsonify({"reply": local_reply(conversation[-1]["content"]), "tools_used": tool_used})


def _cloudflare_vision(image_data_url, prompt, max_tokens=1400, timeout=60):
    """Analisa uma imagem com um modelo multimodal do Workers AI."""
    if not client_configured:
        raise RuntimeError("A análise de imagens precisa da API da Cloudflare configurada.")
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{VISION_MODEL}"
    )
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_token}"},
        json={
            "messages": [
                {"role": "system", "content": "Você é o Cosmo Vision. Analise imagens com atenção. Leia textos visíveis, preserve números e dados importantes e deixe claro quando algo estiver ilegível. Responda em português do Brasil."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            "max_tokens": max_tokens,
            "temperature": 0.15,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json().get("result") or {}
    reply = result.get("response") or result.get("text")
    if not reply:
        raise ValueError("A Cloudflare não retornou uma análise da imagem.")
    return str(reply).strip()


@app.post("/analyze-image")
def analyze_image():
    file = request.files.get("file")
    if not client_configured:
        return jsonify({"error": "A análise de imagens precisa da API da Cloudflare configurada."}), 503
    if not file or not file.filename:
        return jsonify({"error": "Selecione uma imagem."}), 400

    allowed = {
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "image/bmp", "image/tiff"
    }
    mimetype = (file.mimetype or "").lower()
    if mimetype not in allowed:
        return jsonify({"error": "Formato de imagem não suportado. Use JPG, PNG, WEBP, GIF, BMP ou TIFF."}), 415

    raw = file.read(8 * 1024 * 1024 + 1)
    if not raw:
        return jsonify({"error": "A imagem está vazia."}), 400
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"error": "A imagem deve ter no máximo 8 MB."}), 413

    try:
        import base64
        data_url = f"data:{mimetype};base64,{base64.b64encode(raw).decode('ascii')}"
        prompt = str(request.form.get("prompt", "")).strip()[:2000]
        if not prompt:
            prompt = "Analise esta imagem. Descreva o que aparece nela, leia textos importantes e destaque informações úteis."
        reply = _cloudflare_vision(data_url, prompt)
        return jsonify({"reply": reply, "filename": file.filename})
    except Exception:
        app.logger.exception("Erro ao analisar imagem")
        return jsonify({"error": "Não consegui analisar essa imagem. Verifique o arquivo e a configuração da IA visual."}), 502


@app.post("/extract-pdf")
def extract_pdf():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Selecione um arquivo PDF."}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Envie um arquivo PDF."}), 415
    raw = file.read(8 * 1024 * 1024 + 1)
    if not raw:
        return jsonify({"error": "O arquivo está vazio."}), 400
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"error": "O PDF deve ter no máximo 8 MB."}), 413
    try:
        import io
        import base64
        import pypdfium2 as pdfium
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        if len(reader.pages) > 40:
            return jsonify({"error": "O PDF pode ter no máximo 40 páginas."}), 413

        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except TypeError:
                text = page.extract_text() or ""
            parts.append(text)
        extracted = "\n".join(parts).strip()

        # PDF escaneado: usa visão/OCR para interpretar as primeiras páginas.
        if not extracted:
            if not client_configured:
                return jsonify({"error": "Este PDF parece ser escaneado. A leitura visual precisa da API da Cloudflare configurada."}), 503
            doc = pdfium.PdfDocument(raw)
            limit = min(len(doc), 4)
            ocr_parts = []
            for index in range(limit):
                page = doc[index]
                bitmap = page.render(scale=1.0)
                image = bitmap.to_pil()
                image_buffer = io.BytesIO()
                image.save(image_buffer, format="PNG", optimize=True)
                image_bytes = image_buffer.getvalue()
                data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
                page_text = _cloudflare_vision(
                    data_url,
                    f"Faça OCR desta página {index + 1}. Reproduza o texto legível, mantenha números, títulos e tabelas em uma estrutura de texto compreensível. Não invente conteúdo.",
                    max_tokens=1600,
                    timeout=35,
                )
                ocr_parts.append(f"[Página {index + 1}]\n{page_text}")
                bitmap.close()
                page.close()
            doc.close()
            if not ocr_parts:
                return jsonify({"error": "Não consegui ler as páginas do PDF escaneado."}), 422
            extracted = "\n\n".join(ocr_parts)
            return jsonify({
                "text": extracted[:24000],
                "pages": len(reader.pages),
                "truncated": len(extracted) > 24000,
                "ocr": True,
                "ocr_pages": limit,
            })

        return jsonify({
            "text": extracted[:24000],
            "pages": len(reader.pages),
            "truncated": len(extracted) > 24000,
            "ocr": False,
        })
    except Exception:
        app.logger.exception("Erro ao extrair texto do PDF")
        return jsonify({"error": "Não consegui ler o PDF. Verifique se não está protegido, danificado ou em um formato incompatível."}), 422


@app.post("/transcribe")
def transcribe():
    if not client_configured:
        return jsonify({"error": "A transcrição precisa da API da Cloudflare configurada."}), 503

    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"error": "Selecione um arquivo de áudio."}), 400

    allowed = {".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga", ".ogg", ".webm", ".flac"}
    import os as _os
    extension = _os.path.splitext(audio.filename.lower())[1]
    if extension not in allowed:
        return jsonify({"error": "Formato não suportado. Use MP3, WAV, M4A, OGG ou WEBM."}), 415

    raw = audio.read(8 * 1024 * 1024 + 1)
    if not raw:
        return jsonify({"error": "O arquivo está vazio."}), 400
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"error": "O áudio deve ter no máximo 8 MB."}), 413

    try:
        import base64
        encoded = base64.b64encode(raw).decode("ascii")
        model = "@cf/openai/whisper-large-v3-turbo"
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_token}"},
            json={"audio": encoded, "task": "transcribe", "language": "pt"},
            timeout=120
        )
        response.raise_for_status()
        result = response.json().get("result") or {}
        transcript = result.get("text") or result.get("transcription_info", {}).get("text")
        if not transcript:
            raise ValueError("A Cloudflare não retornou uma transcrição.")
        return jsonify({"text": transcript})
    except Exception:
        app.logger.exception("Erro ao transcrever áudio")
        return jsonify({"error": "Não consegui transcrever esse áudio. Tente outro arquivo."}), 502


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
