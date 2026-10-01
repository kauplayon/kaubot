# Cosmo — assistente de IA de Kauplayon

Versão: 1.0 — Em desenvolvimento

Cosmo é um assistente web com IA Cloudflare Workers AI, memória, contexto de conversa, visão, arquivos, ferramentas, pesquisa na web, modo agente, produtividade local e suporte PWA.

## 1.0 Alpha — Cosmo Core
- Memória personalizada opcional.
- Contexto das conversas recentes.
- Ferramentas de calculadora, hora, clima e pesquisa.
- Análise de imagens com modelo multimodal.
- Leitura de PDFs e OCR de PDFs escaneados.
- Transcrição de áudio.

## 1.0 Beta — Cosmo Assistant
- Modo Agente com roteamento de ferramentas.
- Pesquisa na web e contexto de fontes.
- Voz por entrada de áudio e leitura de respostas.
- Tarefas e notas locais.

## 1.0 Release — Cosmo 1.0
- Interface desktop e mobile.
- PWA instalável.
- Perfil local e backup/restauração dos dados.
- Sincronização local entre abas do mesmo navegador.
- Histórico, preferências e memória persistidos no navegador.

## Configuração
Use Python 3.10 ou superior.

Instale:

    pip install -r requirements.txt

Copie `.env.example` para `.env` e configure:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_MODEL`
- `CLOUDFLARE_VISION_MODEL`
- `BOT_NAME`
- `BOT_PERSONALITY`

O projeto usa Cloudflare Workers AI. O modelo visual padrão é `@cf/meta/llama-4-scout-17b-16e-instruct`.

## Pesquisa na web
O modo Agente pode buscar dados usando uma camada de ferramentas do próprio Cosmo. Os resultados podem ser usados como contexto adicional para a resposta.

## Arquivos
- Imagens: até 8 MB.
- PDFs: até 8 MB e 40 páginas.
- PDFs com texto: extração com PyPDF.
- PDFs escaneados: OCR visual limitado às primeiras páginas para controlar custo e processamento.

## PWA e dados
O Cosmo pode ser instalado como PWA em navegadores compatíveis. Conversas, memória, tarefas, notas e preferências ficam no navegador por padrão.

O backup JSON permite transferir manualmente os dados para outro dispositivo. A versão atual não possui autenticação com conta de servidor nem sincronização em nuvem entre dispositivos; isso depende de um backend persistente de autenticação e banco de dados, que fica planejado para uma próxima etapa.

## Segurança
Não publique tokens, chaves de API, senhas ou dados pessoais no GitHub.

## Aviso
O Cosmo pode cometer erros. Confira informações importantes em fontes confiáveis.