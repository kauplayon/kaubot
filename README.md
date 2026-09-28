# Wanda — chatbot de Kauplayon

Chatbot web em português com respostas por IA Gemini, histórico recente e entrada por voz no navegador.

## O que ele faz
- Responde perguntas gerais usando a API Gemini.
- Permite conversar por texto e, em navegadores compatíveis, por voz.
- Mantém as últimas mensagens no contexto durante a sessão.
- Personalidade e modelo configuráveis por variáveis de ambiente.
- Endpoint de saúde em `/health`.

## Configuração local
1. Use Python 3.10 ou superior.
2. Instale as dependências: `pip install -r requirements.txt`.
3. Copie `.env.example` para `.env` e preencha `GEMINI_API_KEY`.
4. Execute `python app.py` e abra `http://127.0.0.1:5000`.

Sem chave, o bot responde apenas a algumas mensagens simples; isso não é uma IA generativa.

## Publicar no Render
Este repositório inclui `render.yaml`. No Render, crie um Blueprint a partir deste repositório e adicione a variável secreta `GEMINI_API_KEY` nas configurações do serviço. O serviço usa `pip install -r requirements.txt` e `gunicorn app:app`.

A hospedagem gratuita pode suspender o serviço após inatividade e pode demorar para iniciar novamente. O reconhecimento de voz depende do navegador e normalmente exige HTTPS.

## Personalização
Configure estas variáveis no servidor (ou no `.env` local):
- `BOT_NAME`: nome exibido e usado pelo assistente (padrão: Wanda).
- `BOT_PERSONALITY`: descrição do jeito de responder (padrão: amigável, paciente, curioso e didático).
- `GEMINI_MODEL`: modelo Gemini (padrão: gemini-2.5-flash).
- `GEMINI_API_KEY`: chave secreta da API; nunca a publique no GitHub.

O projeto usa um modelo Gemini hospedado pela Google; não treina um modelo próprio. A API pode ter limites de uso e condições que mudam. Não envie dados pessoais ou informações confidenciais nas conversas.
