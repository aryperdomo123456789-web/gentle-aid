# Audit Index

Data: 2026-07-27

## Resumo executivo

O problema mais provavel na Central de APIs nao parece ser apenas "chave ausente". O codigo mostra tres pontos de risco bem fortes:

1. O backend faz `autofill_once()` durante o boot da aplicacao, e esse fluxo varre varios diretorios legados, inclusive `/root`, antes de responder a qualquer rota. Isso pode atrasar ou travar o startup do `viral-api` e faz a tela `/apis` ficar em "Carregando..." ate o timeout do frontend. Referencias: `backend/app/__init__.py:33-37`, `backend/app/services/api_keys.py:701-758`, `backend/app/services/api_keys.py:979-1075`.
2. O frontend usa `/api/apis` com timeout proprio de 25s. Se o Flask nao responder dentro desse limite, o usuario ve erro de timeout em vez de dados. Referencia: `src/lib/api.ts:37-57`, `src/routes/apis.tsx:107-116`.
3. O sistema de persistencia depende de `VIRAL_ROOT` e `VIRAL_STORAGE`. Se o ambiente apontar para o diretorio legado `/www/wwwroot/viral.vr766.com` em vez de `/www/wwwroot/gentle-aid`, o cofre pode ir para o lugar errado e o scanner pode buscar nos arquivos antigos. Referencias: `backend/app/config.py:7-31`, `deploy/viral-api.service.template:9-14`, `deploy/viral-web.service.template:9-14`, `backend/app/services/api_keys.py:701-713`, `backend/app/services/api_keys.py:939-975`.

## O que foi confirmado neste auditoria

- O repo local acessivel nao mostra `.env`, `TODASAPI.txt` nem `api_keys.json` versionados no historico. O unico arquivo de ambiente encontrado no historico foi `.env.example`.
- O catalogo atual de provedores esta centralizado em `backend/app/services/api_keys.py:29-312`.
- A rota da Central de APIs e `GET/PUT/DELETE/POST /api/apis...` em `backend/app/blueprints/apis.py:9-82`.
- O frontend da pagina `/apis` consome `/api/apis` e oferece os botoes de importacao, diagnostico e teste em `src/routes/apis.tsx:107-196` e `src/routes/apis.tsx:201-405`.

## Entregaveis deste pacote

- `audit/01-fluxo-e-infra.md`
- `audit/02-inventario-apis.md`
- `audit/03-diagnostico-apis.md`
- `audit/04-plano-correcao.md`
- `audit/05-seguranca-env.md`
- `audit/06-checklist-deploy.md`

## Leitura rapida

Se voce quiser atacar primeiro a causa mais provavel:

1. Confirme se `viral-api` sobe rapido e responde localmente em `127.0.0.1:8000`.
2. Confirme se `nginx` esta fazendo proxy de `/api/` para a porta certa.
3. Confirme se `VIRAL_ROOT` e `VIRAL_STORAGE` apontam para `/www/wwwroot/gentle-aid`.
4. Confirme se o cofre existe em `/www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json` com permissao `600`.
5. Depois disso, valide o `scan_report` da Central de APIs.

