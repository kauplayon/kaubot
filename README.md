# Cosmo — chatbot de Kauplayon

Chatbot web em português com IA Cloudflare Workers AI, histórico local, voz, memória personalizada e leitura de arquivos.

## O que ele faz
- Responde perguntas gerais usando o modelo configurado em CLOUDFLARE_MODEL.
- Permite conversar por texto e, em navegadores compatíveis, por voz.
- Mantém as últimas mensagens de cada conversa no histórico local.
- Oferece modos Normal, Estudos, Tutor e Desenvolvedor.
- Permite editar, regenerar, continuar, copiar e compartilhar respostas.
- Mantém memória personalizada opcional no navegador.
- Lê PDFs com extração de texto e usa visão/OCR para PDFs escaneados quando a IA visual está configurada.
- Analisa imagens enviadas usando um modelo multimodal do Cloudflare Workers AI.
- Transcreve áudio usando Cloudflare Workers AI Whisper.
- Possui interface responsiva para desktop e mobile.
- Endpoint de saúde em /health.

## Configuração local
1. Use Python 3.10 ou superior.
2. Instale as dependências: pip install -r requirements.txt.
3. Copie .env.example para .env.
4. Preencha CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID.
5. Execute python app.py e abra http://127.0.0.1:5000.

A visão usa o modelo definido em CLOUDFLARE_VISION_MODEL. O padrão do projeto é @cf/meta/llama-4-scout-17b-16e-instruct.

Sem as credenciais da Cloudflare, o Cosmo usa apenas o fallback local simples; recursos de IA, visão e transcrição ficam indisponíveis.

## Publicar no Render
Este repositório inclui render.yaml. O serviço usa pip install -r requirements.txt e gunicorn app:app.

No Render, configure:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ACCOUNT_ID
- CLOUDFLARE_MODEL
- CLOUDFLARE_VISION_MODEL

Não publique tokens, chaves ou outros segredos no GitHub.

## Arquivos e IA visual
Imagens podem ter até 8 MB. O Cosmo pode descrever a imagem, responder perguntas sobre ela e extrair textos visíveis.

PDFs continuam limitados a 8 MB e 40 páginas. PDFs com texto usam extração em modo de layout quando disponível. PDFs totalmente escaneados podem usar OCR visual nas primeiras páginas para transformar o conteúdo em texto.

A leitura visual depende da disponibilidade e configuração do modelo multimodal no Workers AI.

## Tecnologias
- Python
- Flask
- HTML, CSS e JavaScript
- Cloudflare Workers AI
- PyPDF
- PyMuPDF

## Aviso
O Cosmo pode cometer erros. Confira informações importantes em fontes confiáveis. Não envie dados pessoais, senhas, chaves de API ou informações confidenciais nas conversas.