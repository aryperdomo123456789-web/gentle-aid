# Memória especializada — Mago API / API Hub do gentle-aid

**Classificação:** documento interno de arquitetura, produto e operação
**Versão:** 0.1.0-draft
**Data:** 26 de agosto de 2026
**Projeto:** `aryperdomo123456789-web/gentle-aid`
**Ambiente auditado:** `38.190.176.171:/www/wwwroot/gentle-aid`
**Autor:** Manus AI

## 1. Propósito desta memória

Este documento preserva as decisões que não podem ficar espalhadas em conversas, commits ou “conhecimento tribal”. Ele é a referência interna para transformar o gentle-aid, hoje um painel de produção de mídia com uma área de geração de chaves, em uma API consumível por outros projetos e operável como produto SaaS.

A memória separa três estados que não podem ser confundidos:

| Estado | Significado |
|---|---|
| **Atual** | O que foi observado no código ou na produção em 26/08/2026 |
| **Proposto** | O contrato e a arquitetura recomendados para a API v1 |
| **Gate** | Condição que precisa estar verde antes de declarar estabilidade |

A regra de ouro é simples: **documentação pública nunca deve anunciar como disponível algo que só existe no plano**. O contrato proposto pode ser versionado e revisado, mas deve conter banner de pré-lançamento até os endpoints passarem pelos gates.

## 2. Contexto do produto

O gentle-aid concentra ferramentas de voz, transcrição, legendagem, dublagem, radar, ingestão e jobs de mídia em um painel servido por Flask/Gunicorn e frontend React/TanStack Start. O documento legado localizado em `/www/wwwroot/viral.vr766.com/legacy/docs/API_HUB_MAGO_GERADOR.md` define o API Hub como ponte entre o painel operacional e um futuro Mago Gerador.

A visão de produto é válida, mas o desenho original misturava catálogo, administração, consumo externo e estado operacional. A API v1 deve separar esses planos:

| Plano | Usuário | Superfície | Regra |
|---|---|---|---|
| Painel | Owner e operadores | UI interna | Sessão web, controles administrativos |
| Controle de acesso | Owner | `/api/access-keys` e tela de chaves | Criar, listar, expirar e revogar tokens |
| Data plane público | Projetos consumidores | `/api/v1/*` | API key, escopo, quota e ownership |
| Operação | Plataforma | métricas, logs, worker, storage | Nunca expor diretamente ao consumidor |

A existência do painel e do controle de acesso não significa que o data plane esteja pronto. A medição feita em produção foi **3/10 para API pública de produção** e **7/10 para o módulo isolado de geração/revogação de chaves**. A diferença é o centro desta memória.

## 3. Estado factual observado

### 3.1 Documentação e runtime

O documento legado descreve `/api-hub`, `/api-hub.json`, `/api-hub/chaves`, `/api/docs`, `/api/openapi.json`, endpoints `/api/public/*` e administração em `/api/admin/api-keys`. Na produção, somente `/api-hub/chaves` respondeu `200`; `/api/public/health`, `/api/public/site`, `/api/public/hub`, `/api/public/catalog`, `/api/public/jobs`, `/api/docs`, `/api/openapi.json`, `/api-hub` e `/api-hub.json` responderam `404`. `/api/access-keys` respondeu `401` sem sessão.[1]

A implementação atual de chaves está em `backend/app/blueprints/release_keys.py` e `backend/app/services/release_keys.py`. O blueprint protege listagem, criação e revogação com sessão owner. O serviço gera token com prefixo `mago_`, usa `secrets.token_urlsafe(32)`, persiste SHA-256, expiração, escopos, revogação e `last_used_at`, e retorna o valor bruto apenas na criação.[2]

### 3.2 Limitação central

`validate_key()` existe, mas a validação aparece como endpoint isolado em `/api/access-keys/validate`. Não há evidência de middleware aplicado às rotas de negócio da API pública, nem de enforcement de escopos nessas rotas. O runtime também não publica as rotas públicas do documento legado. Portanto, a chave é uma base de autenticação, não ainda uma credencial que abre uma API v1 completa.

### 3.3 Riscos herdados que bloqueiam o lançamento

A auditoria anterior confirmou que o Nginx publica a árvore inteira de `fabrica_clips` em `/downloads/`. Requisições `HEAD` externas retornaram `200` para banco de autenticação, cofre de chaves, JSON de jobs, upload de debug e mídia. Rotas internas de jobs e a Central de APIs também apresentam cobertura de autenticação insuficiente.[3]

Esses fatos impedem promover a documentação a stable. Um consumidor externo não pode receber uma API key enquanto a mesma superfície permite acesso direto a dados internos por path conhecido. A correção de exposição e autorização é pré-requisito, não melhoria posterior.

### 3.4 Divergência de versão

Produção está com checkout em `main`, mas o estado de trabalho coincide com o snapshot `origin/backup` e contém mudanças não incorporadas ao `main`. O repositório é público e os branches não estavam protegidos na coleta. O auto-update roda a cada minuto e chama um `update.sh` que usa `git reset --hard`, o que pode remover alterações locais quando `main` avançar.[4]

A API Hub deve ser lançada a partir de uma tag/release única. A documentação não deve apontar para um estado que possa ser destruído por um watcher automático.

## 4. Pesquisa de referências e princípios adotados

As decisões desta memória foram comparadas com referências oficiais de APIs maduras:

| Referência | Princípio absorvido | Aplicação |
|---|---|---|
| Google AIP-151 | Operações demoradas retornam recurso acompanhável | Transcrição retorna job/operation e polling |
| Stripe Idempotent Requests | Retry seguro por chave, mesma resposta e conflito de payload | `Idempotency-Key` em criação/cancelamento |
| Stripe Pagination / Google AIP-158 | Cursor opaco e paginação desde o início | `page_token`/`next_page_token` em listas |
| Google AIP-185 / Stripe Versioning | Major explícita, compatibilidade e depreciação | `/api/v1`, changelog e janela de migração |
| Google AIP-193 / RFC 9457 | Erros estáveis, machine-readable e acionáveis | `application/problem+json` com `type`, `code` e `request_id` |
| OpenAPI 3.1 | Contrato executável para paths, schemas, segurança e callbacks | `api-public-v1.openapi.yaml` como fonte de contrato |
| OpenAI Rate Limits | `429`, `Retry-After`, backoff com jitter e retry limitado | Política por chave/endpoint e cliente resiliente |
| Twilio Webhooks | Callback assinado, resposta rápida, diagnóstico e reentrega | Eventos de job com deduplicação por `event_id` |
| OWASP API Security Top 10 | Object authorization, consumo, SSRF, misconfiguration e inventário | Checklist de release e testes negativos |

Fontes completas e notas de pesquisa estão em `research_api_patterns.md`. A documentação pública cita as fontes oficiais nas seções correspondentes.[5]

## 5. Decisões arquiteturais

### ADR-001 — Separar painel, controle e data plane

**Decisão:** manter o painel web e a geração de chaves como control plane; criar `/api/v1` como data plane versionado e separado.

**Motivo:** o painel usa sessão e privilegia operação humana; consumidores externos precisam de contrato estável, escopos, quotas, ownership, erros e versionamento. Reutilizar diretamente rotas internas cria vazamento de estado, acoplamento a UI e risco de autorização.

**Consequência:** nenhuma rota pública deve chamar diretamente o blueprint administrativo ou devolver o JSON interno de jobs. O data plane deve usar serviços de domínio compartilhados, mas respostas próprias.

### ADR-002 — API key com segredo apresentado uma vez

**Decisão:** manter token bruto somente na resposta de criação; armazenar hash SHA-256, prefixo de identificação, escopos, validade, revogação, owner/tenant e último uso.

**Motivo:** o painel atual já implementa o núcleo correto e segue a prática de não persistir segredo em claro.[2]

**Consequência:** não existe recuperação de chave perdida; o owner revoga e emite outra. Logs, analytics e suporte usam `key_id` e prefixo, nunca token integral.

**Ajuste necessário:** comparar hash com HMAC ou SHA-256 é aceitável para token de alta entropia, mas o serviço deve usar comparação constante quando comparar material derivado e adicionar `tenant_id`, `created_by`, `last_used_at`, `last_used_ip_hash` opcional e status operacional. IP bruto deve ter retenção e base legal definidas.

### ADR-003 — Escopos são allowlist, não decoração

**Decisão:** uma operação declara o escopo exigido; o middleware verifica a interseção entre os escopos da chave e o escopo da operação.

**Exemplo:** `POST /api/v1/transcriptions` exige `transcribe:write`; `GET /api/v1/jobs/{id}` exige `jobs:read`; `GET /result` exige `results:read`.

**Regra:** `public` não deve significar acesso universal a dados; significa somente acesso a endpoints explicitamente marcados como públicos e sem dados de tenant. `admin` nunca deve ser emitido para integração normal.

### ADR-004 — Job é recurso público, arquivo é detalhe interno

**Decisão:** o consumidor recebe `job_id`, estado, progresso, timestamps e URL canônica; nunca recebe caminho físico, JSON de filesystem ou alias Nginx.

**Motivo:** jobs longos precisam sobreviver a requests, retries e reinícios, e dados de resultado precisam de controle de acesso. AIP-151 padroniza a ideia de operação acompanhável.[6]

**Consequência:** resultado sai por endpoint autenticado ou URL assinada com TTL curto. Storage é privado por padrão.

### ADR-005 — Idempotência no perímetro

**Decisão:** toda operação de escrita que pode criar efeito aceita `Idempotency-Key`, com retenção mínima de 24 horas, hash de parâmetros e vínculo a `job_id`.

**Regras:**

| Situação | Resposta |
|---|---|
| Primeira chave e payload válido | Criar job e persistir decisão |
| Retry mesma chave, mesmo consumidor e payload | Retornar mesma resposta/job |
| Mesma chave com payload diferente | `409 IDEMPOTENCY_CONFLICT` |
| Mesma chave em consumidor diferente | Não compartilhar resultado; `409` ou namespace isolado |
| Falha de validação antes de criar efeito | Não gravar operação; cliente pode corrigir/repetir |

O desenho segue a referência de idempotência da Stripe.[7]

### ADR-006 — Erros são contrato

**Decisão:** usar `application/problem+json`, com `type` como identificador estável, `code`, `status`, `title`, `detail`, `request_id`, `retryable` e detalhes opcionais.

**Regra:** `detail` ajuda uma pessoa; `code`/`type` orienta código. Nenhum erro pode conter stack trace, segredo, caminho físico, prompt privado, URL interna ou conteúdo de outro tenant. A decisão segue RFC 9457 e AIP-193.[8]

### ADR-007 — Cursor opaco desde v1

**Decisão:** coleções usam `page_size`, `page_token`, `next_page_token` e `has_more`.

**Regra:** tokens de página são opacos, URL-safe, assinados ou armazenados, e podem expirar. O servidor valida consistência dos filtros. A paginação nasce na primeira versão porque adicioná-la depois pode quebrar consumidores.[9]

### ADR-008 — Versionamento por major no caminho

**Decisão:** iniciar em `/api/v1`; mudanças compatíveis são aditivas; breaking changes entram em `/api/v2` após migração comunicada.

**Regra:** não usar `/v1.1.2`. Preview recebe marca explícita, como `/api/v1-preview`, e nunca deve ser confundido com stable. A decisão segue AIP-185 e práticas de versionamento da Stripe.[10]

### ADR-009 — Webhook opcional, assinado e reentregável

**Decisão:** consumidor pode cadastrar callback HTTPS para eventos terminais de job. Eventos têm `event_id`, timestamp, tipo, payload mínimo e assinatura HMAC.

**Regra:** o receptor deduplica, responde 2xx rapidamente e processa fora do request. O emissor faz retries limitados, expõe tentativa/status e não envia segredo de API no payload. A decisão segue o modelo de callbacks HTTP da Twilio.[11]

## 6. Contrato recomendado da API v1

O contrato completo está em `api-public-v1.openapi.yaml`. A primeira versão deve permanecer pequena.

| Endpoint | Método | Escopo | Resultado |
|---|---|---|---|
| `/health` | GET | nenhum | Saúde sem segredo |
| `/capabilities` | GET | `catalog:read` | Recursos, formatos e limites |
| `/transcriptions` | POST | `transcribe:write` | `202` e job |
| `/jobs` | GET | `jobs:read` | Lista paginada do tenant/chave |
| `/jobs/{job_id}` | GET | `jobs:read` | Estado do próprio job |
| `/jobs/{job_id}/cancel` | POST | `jobs:write` | Solicitação idempotente de cancelamento |
| `/jobs/{job_id}/result` | GET | `results:read` | Resultado protegido |
| `/usage` | GET | `usage:read` | Consumo e limites próprios |

Não adicionar voz, radar, live, TikTok e administração de provedores na v1 até o primeiro fluxo de transcrição ser seguro e observável. Cada novo recurso deve nascer com escopo, ownership, limites, exemplos, schema, erros e testes.

### Fluxo canônico

```text
Cliente
  │ HTTPS + X-API-Key + Idempotency-Key
  ▼
API Gateway / middleware
  │ autentica → verifica expiração/revogação → escopo → quota → ownership
  ▼
POST /v1/transcriptions
  │ persiste idempotência + job
  ├── 202 + job_id + Location
  ▼
Fila persistente
  │ worker de mídia
  ▼
GET /v1/jobs/{id}  ← polling ou webhook assinado
  │
  ├── queued/running
  ├── succeeded → GET /result
  ├── failed
  ├── cancelled
  └── expired
```

## 7. Modelo de dados mínimo

A implementação atual usa SQLite e arquivos locais, mas o data plane deve ter entidades explícitas. O modelo abaixo é lógico e pode começar em SQLite apenas para baixo volume controlado.

### `api_consumers`

| Campo | Regra |
|---|---|
| `id` | ID público interno, não sequencial |
| `name` | Nome do projeto consumidor |
| `status` | `active`, `suspended`, `deleted` |
| `plan` | Plano/quota associada |
| `created_at` | UTC |
| `metadata` | Dados não sensíveis e allowlistados |

### `api_keys`

| Campo | Regra |
|---|---|
| `id` | `rk_...` |
| `consumer_id` | Obrigatório; ownership do tenant |
| `label` | Nome humano |
| `key_prefix` | Apenas identificação parcial |
| `secret_hash` | Único; nunca token bruto |
| `scopes_json` | Allowlist normalizada |
| `created_at` | UTC |
| `expires_at` | Obrigatório; TTL máximo por política |
| `revoked_at` | Nulo quando ativa |
| `last_used_at` | Observabilidade sem segredo |

### `idempotency_records`

| Campo | Regra |
|---|---|
| `consumer_id` | Namespace da chave |
| `idempotency_key` | Única por consumidor e janela |
| `request_hash` | Hash de método, rota e parâmetros seguros |
| `status_code` | Resposta original |
| `response_body` | Corpo seguro, sem segredo |
| `resource_id` | `job_id` gerado |
| `expires_at` | Retenção e cleanup |

### `jobs`

O job precisa carregar `consumer_id`/`api_key_id`, tipo, status, progresso, timestamps, input metadados seguros, resultado lógico, erro estruturado, TTL e idempotency record. Texto de transcrição e URLs de origem devem ter política de privacidade, retenção e acesso. Nunca misturar job público com arquivo de sistema sem uma camada de autorização.

## 8. Middleware de autenticação — comportamento esperado

O middleware deve ser único e reutilizável, não uma série de verificações copiadas em cada blueprint.

```python
def require_api_key(required_scope: str | None = None):
    raw = extract_api_key(request)  # X-API-Key ou Authorization: Bearer
    if not raw:
        raise Problem(401, "AUTHENTICATION_REQUIRED", retryable=False)

    key = key_store.find_by_hash(hash_key(raw))
    if not key or key.revoked_at or key.expires_at <= now_utc():
        raise Problem(401, "INVALID_API_KEY", retryable=False)

    if required_scope and not scope_allows(key.scopes, required_scope):
        raise Problem(403, "MISSING_SCOPE", retryable=False)

    request.api_consumer = key.consumer_id
    request.api_key_id = key.id
    emit_usage_event(key.id, request.path)
```

O pseudocódigo não é implementação pronta. Antes de codificar, definir política de cache curto, invalidação após revogação, concorrência de `last_used_at`, limites, logging e teste de timing. Nunca enviar token ao cliente frontend ou ao browser do painel.

## 9. Rate limit, quota e custo

A API deve limitar por `api_key_id` e também por `consumer_id`. Uma chave revogada precisa deixar de funcionar imediatamente ou dentro de uma janela documentada muito curta. As respostas `429` incluem `Retry-After`; o cliente usa backoff exponencial com jitter e limite de tentativas. Essa prática é consistente com a documentação de rate limits da OpenAI.[12]

| Controle | Primeira política recomendada |
|---|---|
| Requests gerais | 60 RPM por chave, configurável por plano |
| Jobs simultâneos | 2 por chave, configurável |
| Upload | Limite explícito por bytes e duração |
| Idempotência | 24 horas mínimas |
| Resultado | TTL explícito, depois `410 Gone` |
| Webhook retry | Backoff e máximo documentados |
| Quota | Contagem de jobs, bytes, CPU/tempo e armazenamento |

Esses valores são ponto de partida, não promessa comercial. O plano precisa ser configurado em banco/controle operacional e exposto em `/capabilities`/`/usage` sem revelar dados de outros consumidores.

## 10. Segurança obrigatória

A matriz abaixo transforma riscos conhecidos em gates verificáveis.

| Controle | Falha que evita | Teste de aceitação |
|---|---|---|
| Object-level authorization | Consumidor consulta job alheio | Chave A recebe `404` ao consultar job da chave B |
| Function-level authorization | Consumidor acessa admin | Chave comum recebe `403` em admin |
| Property allowlist | Mass assignment/excesso de dados | Campos desconhecidos são ignorados/rejeitados |
| Storage privado | Vazamento de banco/cofre/job | `/downloads/_config/*`, `/_jobs/*` e `/_uploads/*` retornam 404/403 |
| Secret handling | Token em logs ou payload | Scan de logs/payloads não encontra token bruto |
| SSRF defense | Download de rede interna | Loopback, RFC1918, link-local e redirects proibidos |
| Resource quotas | DoS/custo inesperado | Upload grande, duração longa e concorrência excedida retornam erro claro |
| Rate limit | Abuso automatizado | 429 com `Retry-After` e contador observável |
| Revocation | Chave comprometida continua válida | Revogação impede request subsequente |
| Expiration | Chave antiga permanente | Chave vencida retorna 401 |
| Webhook HMAC | Callback forjado | Assinatura inválida é rejeitada sem processar evento |
| TLS/headers | Misconfiguration | TLS moderno, HSTS, CSP e headers testados externamente |

Os riscos foram organizados de acordo com OWASP API1, API2, API3, API4, API5, API7, API8 e API9.[13]

## 11. Observabilidade e SLO

Toda requisição deve gerar `request_id` e registrar métrica de latência, status, endpoint, versão, tenant, chave parcial/ID, bytes e resultado. Logs devem ser estruturados e redigidos. O suporte precisa buscar por `request_id`, `job_id` ou `event_id`, nunca pedir a chave integral.

SLOs só devem ser publicados depois de medir. Como referência interna inicial:

| Indicador | Medição |
|---|---|
| Disponibilidade API | Respostas válidas de `/health` e endpoints de controle |
| Aceitação de job | Tempo entre request válido e `202` |
| Sucesso de worker | Jobs `succeeded` / jobs aceitos |
| P95 de polling | Latência de `GET /jobs/{id}` |
| Tempo de fila | `started_at - created_at` |
| Tempo de processamento | `finished_at - started_at` |
| Webhook delivery | Sucesso por tentativa e tempo até ack |
| Cleanup | Bytes removidos e falhas de retenção |
| Segurança | 401/403/429, scans, incidentes e revogações |

## 12. Deploy e release

A documentação pública só pode avançar quando `main`, backup e produção apontarem para a mesma release. O auto-update destrutivo deve ser desativado antes da primeira implementação do data plane. O release deve seguir esta sequência:

| Etapa | Resultado exigido |
|---|---|
| Design | ADR aprovado e OpenAPI revisado |
| Implementação | Middleware, routes, schemas e storage privado |
| Testes unitários | Hash, expiração, revogação, escopo, idempotência e erros |
| Testes de integração | Cliente externo em staging com arquivo real controlado |
| Testes de segurança | ownership, paths sensíveis, SSRF, rate limit, logs |
| Observabilidade | dashboards, alertas e request IDs |
| Backup | snapshot restaurável e rollback ensaiado |
| Canary | uma chave/test tenant limitado |
| Stable | promoção após janela sem regressão |

## 13. Critérios de aceite da API v1

A v1 só pode ser marcada como stable quando todos os critérios abaixo forem verdadeiros em staging e produção:

1. Um projeto externo consegue criar transcrição com `X-API-Key` sem sessão web.
2. A mesma intenção repetida com a mesma `Idempotency-Key` não cria job duplicado.
3. Chave expirada ou revogada retorna `401` e não chama provedor externo.
4. Chave sem escopo retorna `403` e não inicia job.
5. Uma chave nunca consegue consultar, cancelar ou baixar job de outro consumidor.
6. `POST` retorna `202`, `Location` e estado inicial sem bloquear até o processamento final.
7. Job terminal possui resultado protegido e TTL documentado.
8. `GET /jobs` tem cursor opaco e limite máximo.
9. Erros são `application/problem+json` e incluem `request_id`.
10. `429` inclui `Retry-After` e a documentação explica retry.
11. Webhook inválido não altera estado e evento repetido é deduplicado.
12. OpenAPI valida e os exemplos são executados automaticamente em CI.
13. Nenhum arquivo interno, banco, cofre, upload ou caminho físico responde publicamente.
14. Lint, typecheck, build, testes e scan de dependências passam em ambiente limpo.
15. Há procedimento de revogação, incidente, rollback, retenção e depreciação.

## 14. Roadmap técnico

### Fase 0 — Bloqueio de exposição

Fechar `/downloads/`, remover credenciais padrão, proteger jobs e Central de APIs, restringir scan/import de chaves e rotacionar segredos potencialmente expostos. Sem essa fase, não existe lançamento responsável.

### Fase 1 — API v1 de transcrição

Implementar middleware, consumer/key ownership, `POST /transcriptions`, `GET /jobs/{id}`, `GET /result`, idempotência e Problem Details. Publicar OpenAPI e exemplos em staging.

### Fase 2 — Confiabilidade

Mover execução para fila persistente e worker separado, criar quotas, backpressure, retry por etapa, timeout por recurso, cleanup com TTL e métricas. A fila atual em memória por worker Gunicorn não é suficiente para múltiplos consumidores.

### Fase 3 — Integração

Adicionar webhooks, `/usage`, capabilities, SDK mínimo em Python/Node, ambientes de staging, chaves por tenant e painel de auditoria. Só incluir novos tipos de mídia após o ciclo de transcrição estabilizar.

### Fase 4 — Produto SaaS

Adicionar planos, billing, limites diferenciados, suporte, changelog, depreciação, dashboard de consumo, webhooks configuráveis e clientes gerados a partir do OpenAPI.

## 15. Perguntas abertas que exigem decisão do produto

| Pergunta | Decisão necessária |
|---|---|
| Qual será o domínio oficial? | `viral.vr766.com` ou domínio próprio do Mago API |
| A chave pertence a projeto ou usuário? | Recomenda-se projeto/tenant, com owner humano separado |
| Qual retenção de áudio e texto? | Definir por plano e legislação aplicável |
| Qual política de custo? | Bytes, minutos, CPU ou combinação |
| Haverá webhook no v1? | Recomenda-se iniciar com polling e liberar webhook após assinatura/retry |
| Qual provedor de transcrição? | Abstrair Groq/Whisper e não expor fornecedor ao consumidor |
| Qual fila? | Redis/broker/DB conforme volume e necessidade de recuperação |
| Quem aprova release? | Owner técnico e responsável operacional |
| Qual SLA/SLO público? | Só publicar após medir por janela real |

## 16. Arquivos entregues nesta rodada

| Arquivo | Papel |
|---|---|
| `DOC_PUBLICA_MAGO_API_V1.md` | Guia público de integração, com status draft |
| `api-public-v1.openapi.yaml` | Contrato OpenAPI 3.1 proposto |
| `MEMORIA_ESPECIALIZADA_MAGO_API.md` | Este documento de memória e decisão |
| `research_api_patterns.md` | Notas das referências oficiais pesquisadas |

Nenhum desses documentos altera a produção. Antes de copiar para o repositório, o owner deve decidir se deseja mantê-los em `docs/public-api/` e `docs/internal/`, revisar o domínio/branding e abrir uma release explícita.

## Referências

[1]: ./analysis/api_hub_public_tests.txt
[2]: ./analysis/api_hub_sources/backend/app/services/release_keys.py
[3]: ./analysis/nginx_locations_live.conf
[4]: ./analysis/api_hub_tracking.txt
[5]: ./research_api_patterns.md
[6]: https://google.aip.dev/151
[7]: https://docs.stripe.com/api/idempotent_requests
[8]: https://www.rfc-editor.org/rfc/rfc9457.html
[9]: https://google.aip.dev/158
[10]: https://google.aip.dev/185
[11]: https://www.twilio.com/docs/usage/webhooks
[12]: https://developers.openai.com/api/docs/guides/rate-limits
[13]: https://owasp.org/API-Security/editions/2023/en/0x11-t10/
