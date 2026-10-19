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
- Modo JARVIS opcional com interface HUD futurista e personalidade de assistente pessoal.
- Comandos por voz para abrir produtividade/estatísticas, iniciar conversa, alternar modo JARVIS, criar tarefas e salvar notas.
- HUD cinematográfico JARVIS com painel de status, relógio local e estados de voz.
- Contas com senha armazenada em hash e sincronização de conversas, memória, tarefas, notas e preferências via PostgreSQL.
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
- `SECRET_KEY` (obrigatória para habilitar contas; use uma chave aleatória longa e mantenha-a privada).
- `DATABASE_URL` (URL de conexão de um PostgreSQL persistente; obrigatória para sincronização em nuvem).

O projeto usa Cloudflare Workers AI. O modelo visual padrão é `@cf/meta/llama-4-scout-17b-16e-instruct`.

## Contas e sincronização em nuvem (beta)

1. Crie um banco PostgreSQL persistente e configure DATABASE_URL no serviço do Render usando a URL de conexão adequada.
2. Gere uma chave aleatória longa para SECRET_KEY e cadastre-a como variável secreta no Render. Não use o valor de exemplo de .env.example em produção.
3. O aplicativo cria as tabelas iniciais ao iniciar. A configuração do banco deve estar pronta antes de habilitar o cadastro.
4. Faça deploy e verifique /health: persistent_storage_configured e account_auth_configured devem estar como true.
5. Abra Conta / nuvem, crie sua conta e sincronize os dados locais. O primeiro login combina dados locais e remotos para reduzir o risco de perda de dados.

O Cosmo continua funcionando em modo local quando o banco não está configurado. Nesse caso, cadastro e sincronização em nuvem ficam desabilitados e os dados locais não são apagados. O armazenamento persistente PostgreSQL pode gerar cobrança conforme o plano do provedor; confira os limites e preços atuais antes de ativá-lo.

**Limitações desta versão beta:** ainda não há verificação de e-mail nem fluxo de recuperação de senha. Use uma senha exclusiva e não armazene segredos ou dados altamente sensíveis na memória. Antes de abrir o cadastro ao público, implemente verificação de e-mail e recuperação de conta.

## Pesquisa na web
O modo Agente pode buscar dados usando uma camada de ferramentas do próprio Cosmo. Os resultados podem ser usados como contexto adicional para a resposta.

## Arquivos
- Imagens: até 8 MB.
- PDFs: até 8 MB e 40 páginas.
- PDFs com texto: extração com PyPDF.
- PDFs escaneados: OCR visual limitado às primeiras páginas para controlar custo e processamento.

## PWA e dados
O Cosmo pode ser instalado como PWA em navegadores compatíveis. Conversas, memória, tarefas, notas e preferências ficam no navegador por padrão.

O backup JSON permite transferir manualmente os dados para outro dispositivo. A versão atual não possui autenticação com conta de servidor nem sincronização em nuvem entre dispositivos; isso depende de um backend persistente de autenticação e banco de dados, que fica planejado para uma próxima etapa. O modo JARVIS e os comandos de produtividade também usam os dados locais deste navegador.

## Segurança
Não publique tokens, chaves de API, senhas ou dados pessoais no GitHub.

## Aviso
O Cosmo pode cometer erros. Confira informações importantes em fontes confiáveis.

## Cosmo Command Deck — atualização experimental

A branch `feature/jarvis-3.0-persistent-memory` inclui uma central visual estilo HUD, relógio local, feed de manchetes recentes via Google News RSS e comandos de voz para abrir destinos conhecidos (Google, YouTube, GitHub, Gmail, Maps, entre outros). O feed é atualizado ao carregar e pode ser atualizado manualmente. A disponibilidade depende do acesso do servidor ao RSS e não representa uma garantia de cobertura jornalística em tempo real.

O comando de abertura por voz usa uma lista explícita de sites conhecidos e navega na mesma aba; ele não executa URLs arbitrárias ditadas. Testes automatizados não substituem testes no navegador, microfone e ambiente do Render.
