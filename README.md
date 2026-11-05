# NEXUS — Central de Comando

Interface web futurista em preto, roxo neon e ciano.

## Recursos da versão 1.0

- Dashboard com relógio e data em tempo real
- Núcleo holográfico animado
- Navegação entre módulos
- Gerenciador de tarefas com armazenamento local no navegador
- Atalhos para aplicativos
- Personalização da cor principal
- Layout responsivo para computador e celular
- Endpoint de saúde em `/health`

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

No Windows, ative o ambiente com `.venv\\Scripts\\activate`.

Acesse `http://localhost:5000`.

## Publicar

O projeto está preparado para deploy no Render usando Gunicorn e o arquivo `render.yaml`.

## Observação

Nesta versão, os módulos de IA, clima e notícias são apenas áreas planejadas na interface. Ainda não há integrações externas nem monitoramento real do dispositivo.
