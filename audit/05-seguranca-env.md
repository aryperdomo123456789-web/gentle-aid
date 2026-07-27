# Seguranca de `.env` e chaves

## Regra principal

Chave real nunca deve ficar versionada. O repo pode manter apenas:

- `.env.example`
- docs
- codigo que sabe ler `api_keys.json` e o `.env` do servidor

## Arquivo correto no servidor

### `.env`

Local:

- `/www/wwwroot/gentle-aid/.env`

Permissao esperada:

- `0600`

Owner esperado:

- o mesmo usuario do `viral-api` e do `viral-web`

Referencia:

- `deploy/viral-api.service.template:7-14`
- `deploy/viral-web.service.template:7-14`
- `backend/app/services/api_keys.py:939-975`

### `api_keys.json`

Local:

- `/www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json`

Permissao esperada:

- `0600`

Referencia:

- `backend/app/services/api_keys.py:321-343`

## `.gitignore`

O repo ja ignora os principais artefatos sensiveis:

- `.env`
- `fabrica_clips/`
- `frontend_dist/`
- `backend/api_keys.json`
- `__pycache__/`
- `.venv/`

Referencia: `.gitignore:1-33`

## Ponto que merece reforco

Mesmo com `fabrica_clips/` ignorado, vale garantir que o caminho especifico do cofre esteja sempre fora do Git e fora do build:

- `fabrica_clips/_config/api_keys.json`

## Como o systemd deve carregar

O backend e o frontend leem `EnvironmentFile=-__APP_DIR__/.env`.

Referencias:

- `deploy/viral-api.service.template:9-14`
- `deploy/viral-web.service.template:9-14`

Isso significa:

- o `.env` do servidor e a fonte de configuracao
- o boot nao deve depender de arquivo versionado

## Rotacao das chaves vazadas

Se qualquer chave publica do repo legado tiver sido exposta fora do Git, rotacione todas as que estiverem no inventario antes de confiar no ambiente atual.

### Ordem recomendada

1. Gemini
2. Hugging Face
3. Cloudflare
4. Groq
5. OpenRouter
6. DeepSeek
7. Tavily
8. Exa
9. Firecrawl
10. Jina
11. Langfuse
12. Whisper
13. TikAPI
14. Lamatok
15. Mistral
16. Cohere

### Procedimento generico

1. Revogar a chave antiga no dashboard do provedor.
2. Emitir uma chave nova.
3. Atualizar o cofre do servidor.
4. Rodar teste de conectividade na Central de APIs.
5. Conferir se `masked` mudou e se `last_test.ok` ficou `true`.
6. Remover qualquer copia em `.env.example`, notas e issues antigas.

### Observacoes por provedor

- Gemini: usar chave de AI Studio que comece com `AIza`.
- Hugging Face: usar token `Read`.
- Cloudflare: preferir API Token moderno; se usar Global API Key, tambem precisa de `CLOUDFLARE_EMAIL`.
- TikAPI: 403 costuma ser assinatura/plano expirado.
- Lamatok: 402 normalmente e credito zerado, nao token invalido.

## Cuidado com o espelhamento automatico

O codigo atual espelha chaves do cofre para `.env` em `sync_env()`. Isso pode ser util, mas tambem amplia o impacto de um erro de permissao ou path errado.

Referencia: `backend/app/services/api_keys.py:939-975`.

Se o Lovable for mexer nisso, o ideal e:

- deixar o cofre como fonte primaria
- restringir o espelho `.env` a administracao/deploy
- nunca gravar segredos no repo

