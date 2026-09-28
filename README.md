# KauBot — chatbot de Kauplayon

Chatbot web em português, com histórico de conversa, respostas usando a API Gemini e entrada por voz no navegador.

## Requisitos
- Python 3.10 ou superior
- Chave da API Gemini (há opção gratuita sujeita a limites e disponibilidade)

## Executar localmente
1. Crie e ative um ambiente virtual.
2. Instale as dependências: `pip install -r requirements.txt`
3. Copie `.env.example` para `.env` e coloque sua chave em `GEMINI_API_KEY`.
4. Execute: `python app.py`
5. Abra `http://127.0.0.1:5000`.

Sem chave, o app inicia em modo básico baseado em regras; isso não é um modelo de IA generativa. O reconhecimento de voz depende do navegador e pode exigir conexão segura quando hospedado.

## Publicar no GitHub
Crie um repositório chamado `kaubot` na conta `kauplayon` e envie os arquivos deste projeto. Não envie o arquivo `.env` nem publique sua chave. Para hospedar o site, configure a variável `GEMINI_API_KEY` nas configurações de ambiente da plataforma de hospedagem.

## Sobre o modelo
Este projeto usa um modelo Gemini hospedado pela Google por meio de API; não treina um modelo próprio. Treinar um modelo generativo do zero exige dados e recursos computacionais consideráveis.
