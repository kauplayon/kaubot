import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

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

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_configured": client_configured,
        "vision_configured": client_configured,
        "version": "0.9 — Em desenvolvimento"
    })

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return jsonify({"reply": "Envie uma pergunta para começarmos."}), 400

    study_mode = bool(data.get("study_mode"))
    assistant_mode = str(data.get("assistant_mode", "normal"))
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
    system_prompt = SYSTEM + "\\nPersonalidade escolhida: " + personality + "\\nResponda sempre no idioma: " + language + "."
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
        system_prompt += "\nPreferências que o usuário escolheu salvar: " + memory
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
                json={"messages": conversation, "max_tokens": 2048},
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
        import fitz
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
            doc = fitz.open(stream=raw, filetype="pdf")
            limit = min(len(doc), 6)
            ocr_parts = []
            for index in range(limit):
                page = doc.load_page(index)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.15, 1.15), alpha=False)
                image_bytes = pix.tobytes("png")
                data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
                page_text = _cloudflare_vision(
                    data_url,
                    f"Faça OCR desta página {index + 1}. Reproduza o texto legível, mantenha números, títulos e tabelas em uma estrutura de texto compreensível. Não invente conteúdo.",
                    max_tokens=2200,
                    timeout=45,
                )
                ocr_parts.append(f"[Página {index + 1}]\n{page_text}")
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
