# Estado atual do projeto

Data do snapshot: `2026-08-07`

Este documento registra o estado atual do repositório em `/www/wwwroot/gentle-aid`
antes da sincronização com o GitHub.

## Visão geral

O projeto é o **Ecossistema Viral**, um painel web para operação de mídia com:

- frontend em React 19 + TanStack Start;
- backend em Flask com blueprints modulares;
- deploy previsto para aaPanel com Nginx, Gunicorn e Node;
- armazenamento local de jobs, histórico e chaves fora do Git.

O acesso público observado em `https://viral.vr766.com/login` responde como
**“Painel Admin — Ecossistema Viral”** e exibe o carregamento do acesso seguro.

## Estado funcional atual

O estado atual do código já inclui a área de **Chaves de Acesso** para emissão,
listagem, revogação e validação de credenciais de liberação.

### Backend

- `backend/app/__init__.py`
  - registra o blueprint de chaves de liberação;
  - mantém os blueprints existentes do painel;
  - expõe `GET /api/health` e `GET /api/version`;
  - reconcilia jobs órfãos e sessões de live no boot.
- `backend/app/blueprints/release_keys.py`
  - cria o endpoint `/api/access-keys`;
  - protege listagem, criação e revogação com acesso de `owner`;
  - expõe validação pública em `POST /api/access-keys/validate`.
- `backend/app/services/release_keys.py`
  - cria a tabela `release_keys` em SQLite;
  - gera chaves com prefixo `mago_`;
  - armazena apenas hash, prefixo, escopos, validade e revogação;
  - atualiza `last_used_at` ao validar uma chave ativa.

### Frontend

- `src/components/TopNav.tsx`
  - adiciona o atalho para `/api-hub/chaves`.
- `src/features/access-keys/api.ts`
  - centraliza chamadas para listar, criar e revogar chaves.
- `src/features/access-keys/types.ts`
  - define os tipos do domínio de chaves de acesso.
- `src/routes/api-hub/chaves.tsx`
  - cria a tela de administração das chaves;
  - mostra estatísticas, formulário de criação e lista de chaves;
  - permite copiar a chave bruta apenas no momento da criação.
- `src/routes/apis.tsx`
  - integra a Central de APIs ao fluxo do painel.
- `src/routeTree.gen.ts`
  - foi regenerado para incluir a nova rota.

## Rotas relevantes

- `/login` - acesso ao painel.
- `/apis` - Central de APIs.
- `/api-hub/chaves` - gestão de chaves de acesso.
- `/api/access-keys` - API administrativa das chaves.
- `/api/access-keys/validate` - validação de chave.

## Observações de operação

- O remoto `origin` aponta para `git@github-gentle-aid:aryperdomo123456789-web/gentle-aid.git`.
- O branch local atual é `main`.
- O branch remoto `backup` já existe e será usado como espelho do snapshot atual.
- A documentação principal do projeto continua em `README.md`.
- O arquivo `src/routes/README.md` descreve as convenções de rotas do TanStack Start.

## Itens ainda não verificados aqui

- Login autenticado com conta real.
- Execução completa de build e runtime do backend no servidor atual.
- Fluxo de validação da chave com credenciais reais de produção.

## Resumo curto

O repositório local já está preparado para publicar a funcionalidade de
chaves de acesso e a navegação correspondente. Este arquivo serve como
snapshot documental do estado do projeto no momento da sincronização.
