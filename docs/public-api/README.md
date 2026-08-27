# Mago API v1

## Documentação pública de integração

**Versão do documento:** 0.1.0-alpha
**Status:** alpha controlada — transcrição v1, envelope de operação longa, fila persistente e limites por consumidor publicados; expansão comercial ainda condicionada aos gates operacionais
**Última revisão:** 27 de agosto de 2026
**Base prevista:** `https://viral.vr766.com/api/v1`

> **Aviso de disponibilidade.** Este documento descreve a Mago API v1 em alpha controlada. `GET /api/v1/health`, `GET /api/v1/capabilities`, `POST /api/v1/transcriptions`, consulta/cancelamento de operações, entrega protegida e OpenAPI estão publicados no ambiente principal. Rate limit, quota diária e fila persistente estão ativos com valores conservadores; não há SLA comercial. Consulte a seção [Estado de lançamento](#estado-de-lançamento) antes de iniciar uma integração.

## Visão geral

A Mago API será a camada externa do gentle-aid para que outros produtos criem e acompanhem operações de processamento de mídia sem depender da interface do painel. A primeira versão será deliberadamente pequena: saúde, capacidades, transcrição assíncrona, consulta/cancelamento de jobs, entrega protegida de resultados e consumo do próprio consumidor.

O contrato segue princípios usados por APIs maduras: operações longas retornam um recurso consultável em vez de bloquear o request [1], POSTs que criam efeitos aceitam idempotência [2], coleções usam cursores [3], erros são machine-readable [4] [5], e mudanças incompatíveis exigem uma nova versão [6].

## Estado de lançamento

A API Hub documentada no legado prevê uma camada com `X-API-Key`, `Authorization: Bearer`, catálogo e endpoints públicos. A implementação atual tem uma tela owner para gerar e revogar chaves em `/api-hub/chaves`, um endpoint administrativo interno em `/api/access-keys` e a superfície pública alpha em `/api/v1`. O envelope de operação longa foi adicionado sem remover os aliases `/jobs/*`; limites técnicos por chave estão ativos, enquanto billing, planos, webhooks e SLA comercial continuam fora da garantia alpha.

Até que o checklist abaixo esteja verde, a documentação deve permanecer marcada como **Alpha**:

| Gate | Obrigatório para anunciar v1 | Situação observada |
|---|---|---|
| Middleware de API key aplicado às rotas | Cada rota protegida valida token, expiração, revogação e escopo | Implementado |
| Endpoint público de transcrição | `POST /api/v1/transcriptions` responde 202 e cria job isolado | Publicado em alpha |
| Consulta segura | Consumidor só vê operações criadas pela sua chave | Implementado |
| Resultado protegido | Nenhum caminho físico ou arquivo interno é público | Implementado; outputs legados em migração |
| OpenAPI publicado | `/api/docs` e `/api/openapi.json` refletem o runtime | Publicado |
| Limites | Rate limit, quota de upload, concorrência e custo definidos | Implementado com defaults conservadores e configuração por ambiente |
| Idempotência | Retry do mesmo POST não duplica job | Implementado e testado |
| Testes | Autorização, isolamento, erro, retry, expiração, fila e limites cobertos | Contrato, fila e limites cobertos; provider real e carga pendentes |

## URL base e versões

Quando liberada, a API estável será servida sob `/api/v1`. A versão major fica no caminho para tornar a compatibilidade explícita. Mudanças aditivas e compatíveis entram em `v1`; alterações incompatíveis exigem `v2`, período de depreciação e comunicação prévia. A API não usará `v1.1.2` no caminho.

| Ambiente | URL | Uso |
|---|---|---|
| Produção | `https://viral.vr766.com/api/v1` | Consumidores reais, somente após lançamento |
| Homologação | `https://staging.viral.vr766.com/api/v1` | Integração e testes, substituir pelo host definitivo |

O servidor pode aceitar `X-API-Version` no futuro para experimentos de compatibilidade, mas a versão canônica desta primeira proposta é o prefixo `/v1`. A política segue a recomendação de manter versões compatíveis simultaneamente e comunicar depreciações [6].

## Autenticação

A API usa uma chave de acesso por consumidor. A chave completa começa com `mago_` e deve ser tratada como senha: não deve aparecer em código-fonte, logs, analytics, query string, tickets ou screenshots. O painel mostra o segredo integral somente no momento da criação; o servidor armazena apenas hash.

### Header recomendado

```http
X-API-Key: mago_<sua-chave>
```

### Alternativa Bearer

```http
Authorization: Bearer mago_<sua-chave>
```

Envie a chave somente por HTTPS. Não use `/api/access-keys` ou a interface owner no código do consumidor; essas superfícies são administrativas. A aplicação consumidora deve armazenar o token em secret manager ou variável de ambiente protegida.

### Idempotência e correlação são coisas diferentes

`Idempotency-Key` é um identificador da **intenção de escrita**. Ele é obrigatório para criar ou cancelar operações, é armazenado junto do consumidor e do fingerprint do payload e serve para que um retry não crie um segundo job. A mesma chave com o mesmo payload devolve a mesma decisão; a mesma chave com payload diferente devolve `409 IDEMPOTENCY_CONFLICT`.

`X-Request-Id` é um identificador de **uma requisição HTTP específica**. Ele é gerado pelo servidor, devolvido na resposta e usado para suporte, logs e rastreabilidade. Cada tentativa pode receber um novo `X-Request-Id`, inclusive quando o servidor devolve um replay idempotente. O cliente não deve usar esse valor para deduplicação e não deve depender de seu conteúdo.

`X-Client-Request-Id` é opcional e serve apenas para o consumidor correlacionar a chamada com seu próprio sistema. Ele não altera o fingerprint de idempotência. Um valor enviado pelo cliente no header `X-Request-Id` também não controla o identificador retornado pela API.

### Escopos

A chave receberá apenas os escopos necessários. A tabela abaixo é o vocabulário inicial proposto:

| Escopo | Permite |
|---|---|
| `catalog:read` | Ler capacidades e limites públicos do consumidor |
| `transcribe:write` | Criar transcrições |
| `jobs:read` | Consultar jobs pertencentes à chave |
| `jobs:write` | Solicitar cancelamento dos próprios jobs |
| `results:read` | Obter resultados dos próprios jobs |
| `usage:read` | Consultar uso e limites da própria chave |
| `public` | Acesso somente a recursos explicitamente marcados como públicos |
| `admin` | Reservado para operação interna; nunca emitir para integração comum |

Escopo armazenado não é escopo aplicado. Uma rota só está protegida quando o middleware valida o escopo antes de executar a operação.

## Criar uma transcrição

`POST /api/v1/transcriptions` recebe um arquivo de áudio ou vídeo e cria uma operação assíncrona. O cliente deve enviar uma `Idempotency-Key` nova para cada intenção de criação. Se houver timeout de rede, repita o mesmo request com a mesma chave; não gere outra chave antes de saber se a primeira operação foi criada. A resposta usa o envelope canônico `Operation`, inspirado na semântica de operações longas do AIP-151 [13].

```bash
curl -X POST "https://viral.vr766.com/api/v1/transcriptions" \
  -H "X-API-Key: ${MAGO_API_KEY}" \
  -H "Idempotency-Key: 7b8d5b25-4a9e-4de3-9b34-3dca6b7f9f4d" \
  -H "X-Client-Request-Id: checkout-82731" \
  -F "file=@video.mp4" \
  -F "language=pt" \
  -F "output_format=srt"
```

Resposta esperada quando o contrato estiver publicado:

```http
HTTP/1.1 202 Accepted
Location: https://viral.vr766.com/api/v1/operations/api-transcription-01J7MAGOTRANSCRIBE
X-Request-Id: req_01J7MAGOACCEPTED
Content-Type: application/json
```

```json
{
  "name": "operations/api-transcription-01J7MAGOTRANSCRIBE",
  "id": "api-transcription-01J7MAGOTRANSCRIBE",
  "object": "operation",
  "type": "transcription",
  "done": false,
  "status": "PENDING",
  "metadata": {
    "progress": 0,
    "stage": "queued",
    "created_at": "2026-08-26T23:45:00Z",
    "expires_at": "2026-08-29T23:45:00Z"
  },
  "response": null,
  "error": null,
  "poll_url": "https://viral.vr766.com/api/v1/operations/api-transcription-01J7MAGOTRANSCRIBE",
  "progress": 0,
  "stage": "queued",
  "created_at": "2026-08-26T23:45:00Z",
  "finished_at": null,
  "expires_at": "2026-08-29T23:45:00Z",
  "result_url": null,
  "api_version": "v1"
}
```

### Campos do upload

| Campo | Obrigatório | Tipo | Regra inicial |
|---|---:|---|---|
| `file` | Sim | binário | Áudio ou vídeo dentro do limite da chave |
| `language` | Não | string | Código curto, por exemplo `pt`, `en` ou `es` |
| `output_format` | Não | enum | `srt`, `vtt`, `json` ou `text`; default `srt` |
| `webhook.url` | Não | URL | HTTPS público do consumidor |
| `webhook.secret` | Não | string | Segredo HMAC com pelo menos 32 caracteres; nunca devolvido |
| `webhook.events` | Não | array | `job.completed`, `job.failed`, `job.cancelled` |

Os limites exatos de tamanho, duração, concorrência e retenção devem ser retornados em `/capabilities` e `/usage`. O consumidor não deve assumir que o limite do painel interno vale para a API externa.

## Idempotência

Todo POST que cria job deve aceitar `Idempotency-Key`. A chave deve ser uma UUID v4 ou identificador aleatório sem dados pessoais. Para a mesma chave, consumidor e payload, a API devolve a mesma decisão e o mesmo job. Se a mesma chave for reutilizada com payload diferente, a resposta é `409` com `IDEMPOTENCY_CONFLICT`.

A retenção mínima recomendada para a tabela de idempotência é 24 horas. A API deve persistir o hash do payload, status, corpo seguro da resposta e `job_id`; nunca deve guardar arquivo duplicado apenas para repetir uma resposta. O padrão acompanha a prática da Stripe de comparar parâmetros e tornar retries seguros [2].

## Consultar uma operação

Novas integrações devem consultar o recurso canônico:

```bash
curl "https://viral.vr766.com/api/v1/operations/api-transcription-01J7MAGOTRANSCRIBE" \
  -H "X-API-Key: ${MAGO_API_KEY}" \
  -H "X-Client-Request-Id: poll-82731"
```

`GET /api/v1/jobs/{job_id}` permanece como alias compatível e devolve o mesmo envelope. O consumidor só recebe operações pertencentes à sua chave ou ao tenant associado. Para não revelar a existência de IDs de terceiros, a API pode responder `404` tanto para uma operação inexistente quanto para uma operação de outro consumidor.

Estados públicos possíveis:

| Estado | Significado | Terminal |
|---|---|---:|
| `PENDING` | Aceita e aguardando worker | Não |
| `RUNNING` | Em processamento | Não |
| `SUCCEEDED` | Resultado disponível | Sim |
| `FAILED` | Falha permanente ou tentativas esgotadas | Sim |
| `CANCELLED` | Cancelada pelo consumidor ou operador | Sim |
| `EXPIRED` | Resultado removido pela retenção | Sim |

O campo `done` é falso em `PENDING` e `RUNNING`, e verdadeiro em estados terminais. O cliente deve fazer polling com backoff, respeitando `Retry-After` quando fornecido. Não faça polling agressivo a cada segundo por horas; use o webhook quando precisar de notificação imediata. Clientes devem ignorar campos desconhecidos e tolerar novos estados em versões compatíveis.

## Listar jobs

`GET /api/v1/jobs` lista somente os jobs do consumidor autenticado. O contrato usa cursor opaco, não offset:

```bash
curl "https://viral.vr766.com/api/v1/jobs?page_size=50&status=succeeded" \
  -H "X-API-Key: ${MAGO_API_KEY}"
```

```json
{
  "data": [
    {
      "id": "job_01J7MAGOTRANSCRIBE",
      "object": "job",
      "type": "transcription",
      "status": "succeeded",
      "progress": 100,
      "created_at": "2026-08-26T23:45:00Z",
      "finished_at": "2026-08-26T23:47:20Z",
      "result_url": "https://viral.vr766.com/api/v1/jobs/job_01J7MAGOTRANSCRIBE/result"
    }
  ],
  "has_more": false,
  "next_page_token": null
}
```

`page_size` tem default 50 e máximo 100. `next_page_token` é opaco e pode expirar. Filtros usados na primeira página devem permanecer iguais nas páginas seguintes. Esse desenho segue as orientações de paginação da Stripe e do Google [3] [9].

## Cancelar uma operação

Novas integrações devem usar o método canônico:

```bash
curl -X POST "https://viral.vr766.com/api/v1/operations/api-transcription-01J7MAGOTRANSCRIBE:cancel" \
  -H "X-API-Key: ${MAGO_API_KEY}" \
  -H "Idempotency-Key: cancel-7b8d5b25-4a9e-4de3-9b34-3dca6b7f9f4d"
```

`POST /api/v1/jobs/{job_id}/cancel` permanece como alias compatível. A resposta `202` confirma que a solicitação de cancelamento foi aceita, não necessariamente que o processo já terminou. Consulte a operação até que o estado seja `CANCELLED` ou outro estado terminal. Cancelar uma operação já concluída é uma operação sem efeito ou retorna `409`, conforme o estado definido pelo contrato.

## Obter o resultado

```bash
curl "https://viral.vr766.com/api/v1/jobs/job_01J7MAGOTRANSCRIBE/result?format=srt" \
  -H "X-API-Key: ${MAGO_API_KEY}" \
  -o legenda.srt
```

A API nunca deve devolver caminho físico do servidor, nome interno de pasta, JSON privado de job ou link permanente sem autorização. O resultado pode ser transmitido pela API ou entregue por URL assinada com expiração curta. Depois do TTL, o resultado retorna `410 Gone` e o consumidor precisa reenviar o job.

## Rate limit, quotas e custo

As rotas autenticadas aplicam um limite fixo por API key e devolvem headers de transparência quando a chave é válida:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-Quota-Jobs-Limit: 100
X-Quota-Jobs-Used: 1
X-Quota-Audio-Seconds-Limit: 3600
X-Quota-Audio-Seconds-Used: 42
X-Quota-Cost-Units-Limit: 3600
X-Quota-Cost-Units-Used: 1
```

Os defaults são política técnica de alpha, não preço comercial. `cost_units` é uma estimativa interna baseada em minutos de áudio; não representa a fatura final do provider. Quando o limite é excedido, a API responde `429` com `Retry-After` e um código estável: `RATE_LIMIT_EXCEEDED`, `DAILY_JOB_QUOTA_EXCEEDED`, `DAILY_AUDIO_QUOTA_EXCEEDED` ou `DAILY_COST_LIMIT_EXCEEDED`. `/usage` expõe o uso da própria chave.

## Webhooks

O consumidor pode informar um webhook no momento da criação. A API envia um POST assinado quando o job atingir estado terminal. O endpoint do consumidor deve:

1. validar assinatura e timestamp antes de processar;
2. deduplicar pelo `event.id`;
3. responder `2xx` rapidamente;
4. enfileirar o processamento próprio fora do request;
5. tolerar reentrega do mesmo evento;
6. registrar o `X-Request-Id` e o `event.id`.

Payload:

```json
{
  "id": "evt_01J7MAGOEVENT",
  "type": "job.completed",
  "created_at": "2026-08-26T23:47:20Z",
  "data": {
    "job": {
      "id": "job_01J7MAGOTRANSCRIBE",
      "status": "succeeded",
      "result_url": "https://viral.vr766.com/api/v1/jobs/job_01J7MAGOTRANSCRIBE/result"
    }
  }
}
```

Headers propostos:

```http
X-Mago-Event-Id: evt_01J7MAGOEVENT
X-Mago-Event-Timestamp: 2026-08-26T23:47:20Z
X-Mago-Signature: sha256=<hex>
```

Webhooks são callbacks HTTP e devem ser tratados como eventos potencialmente repetidos; esse modelo segue a prática descrita na documentação da Twilio para integrações orientadas a eventos [10].

## Rate limits, quotas e retry

Limites serão aplicados por API key e endpoint. A resposta `429` deve incluir `Retry-After` em segundos. O cliente deve usar exponential backoff com jitter, limitar tentativas e distinguir erros transitórios de erros permanentes, conforme a orientação da OpenAI [11].

| Resposta | Retry automático? | Ação do cliente |
|---|---:|---|
| `400` | Não | Corrigir payload |
| `401` | Não | Corrigir ou rotacionar credencial |
| `403` | Não | Solicitar escopo ou acesso adequado |
| `404` | Não | Conferir ID/ownership/versão |
| `409` | Condicional | Resolver estado ou conflito de idempotência |
| `413` | Não | Reduzir arquivo ou solicitar limite adequado |
| `415` | Não | Enviar tipo suportado |
| `422` | Não | Corrigir conteúdo semanticamente inválido |
| `429` | Sim, com limite | Esperar `Retry-After` e backoff com jitter |
| `500` | Condicional | Repetir com a mesma idempotência se for POST |
| `502`/`503`/`504` | Sim, limitado | Retry com backoff; respeitar `Retry-After` |

O endpoint `/usage` deve permitir ao consumidor acompanhar requests, jobs, bytes e concorrência. Quotas de CPU, disco, duração e custo devem existir antes de a API aceitar tráfego de terceiros.

## Erros

Erros usam `Content-Type: application/problem+json`, inspirados no RFC 9457 [5]. O consumidor deve programar contra `type` ou `code`, não contra o texto de `detail`.

```json
{
  "type": "https://viral.vr766.com/problems/idempotency-conflict",
  "title": "Idempotency key conflict",
  "status": 409,
  "code": "IDEMPOTENCY_CONFLICT",
  "detail": "The Idempotency-Key was already used with different parameters.",
  "instance": "/api/v1/transcriptions",
  "request_id": "req_01J7MAGOERROR",
  "retryable": false,
  "retry_after_seconds": null,
  "field_errors": []
}
```

Mensagens devem ser curtas e acionáveis. Nunca retornam stack trace, segredo, URL de provedor interno, caminho de disco, conteúdo de transcrição de outro consumidor ou hash de credencial.

## Observabilidade e suporte

Toda resposta deve incluir `X-Request-Id`. O consumidor deve guardar esse identificador junto com horário, endpoint e status. O suporte deve conseguir localizar uma requisição sem pedir a chave integral. Logs internos devem armazenar apenas hash/ID da chave, tenant, endpoint, status, latência e bytes; a chave completa nunca entra em log.

## Segurança do consumidor

A chave deve viver em um secret manager. O consumidor deve evitar expor a credencial no frontend, em repositório, em parâmetros de URL, em mensagens de erro e em logs de CI. Para ambientes distintos, use chaves distintas; revogue uma chave comprometida sem invalidar todos os consumidores.

A Mago API também deve bloquear ownership quebrado, consumo irrestrito, SSRF, configurações inseguras e inventário incompleto, riscos destacados pelo OWASP API Security Top 10 [12].

## Compatibilidade e depreciação

Campos novos serão adicionados de forma compatível. Consumidores devem ignorar campos desconhecidos e tratar enums como potencialmente extensíveis. Remover ou renomear campos, mudar semântica, alterar autenticação ou mudar estado de job exige nova major ou período formal de migração. O changelog público deve registrar data, impacto, versão afetada, substituição e data prevista de desligamento.

## Exemplos de integração

### Python

```python
import os
import time
import uuid
import requests

BASE_URL = "https://viral.vr766.com/api/v1"
HEADERS = {
    "X-API-Key": os.environ["MAGO_API_KEY"],
    "Idempotency-Key": str(uuid.uuid4()),
}

with open("video.mp4", "rb") as media:
    response = requests.post(
        f"{BASE_URL}/transcriptions",
        headers=HEADERS,
        files={"file": ("video.mp4", media, "video/mp4")},
        data={"language": "pt", "output_format": "srt"},
        timeout=60,
    )
response.raise_for_status()
job = response.json()

while not job["done"]:
    time.sleep(5)
    poll = requests.get(
        job["poll_url"],
        headers={"X-API-Key": os.environ["MAGO_API_KEY"]},
        timeout=30,
    )
    poll.raise_for_status()
    job = poll.json()

if job["status"] == "SUCCEEDED":
    result = requests.get(
        job["result_url"],
        headers={"X-API-Key": os.environ["MAGO_API_KEY"]},
        timeout=30,
    )
    result.raise_for_status()
    open("legenda.srt", "wb").write(result.content)
else:
    raise RuntimeError(job["error"] or "A operação terminou sem resultado")
```

O exemplo é ilustrativo. Ele só deve ser executado quando os endpoints da v1 e seus limites estiverem publicados em homologação.

### Node.js

```js
import fs from "node:fs";
import crypto from "node:crypto";

const base = "https://viral.vr766.com/api/v1";
const key = process.env.MAGO_API_KEY;
const idempotencyKey = crypto.randomUUID();

const body = new FormData();
body.append("file", new Blob([fs.readFileSync("video.mp4")]), "video.mp4");
body.append("language", "pt");
body.append("output_format", "srt");

const created = await fetch(`${base}/transcriptions`, {
  method: "POST",
  headers: { "X-API-Key": key, "Idempotency-Key": idempotencyKey },
  body,
});
const job = await created.json();
console.log(job.id, job.status, job.poll_url);
```

## Estado de lançamento

A documentação poderá ser promovida de `draft` para `stable` apenas quando:

| Área | Critério |
|---|---|
| Segurança | Nenhum arquivo interno acessível por `/downloads/`; rotas privadas com testes negativos |
| Auth | API key validada em middleware, escopo aplicado, expiração e revogação testadas |
| Jobs | Ownership por tenant/chave, fila persistente, idempotência e cancelamento verificáveis |
| Contrato | OpenAPI validado, docs renderizadas, exemplos executados em staging |
| Operação | Rate limits, quotas, métricas, alertas, backup e rollback ensaiados |
| Qualidade | CI verde para lint, typecheck, build, testes e scan de dependências |
| Produto | Política de retenção, suporte, changelog e depreciação publicados |

## Referências

[1]: https://google.aip.dev/151
[2]: https://docs.stripe.com/api/idempotent_requests
[3]: https://docs.stripe.com/api/pagination
[4]: https://google.aip.dev/193
[5]: https://www.rfc-editor.org/rfc/rfc9457.html
[6]: https://google.aip.dev/185
[7]: ./analysis/API_HUB_MAGO_GERADOR.md
[8]: ./analysis/api_hub_public_tests.txt
[9]: https://google.aip.dev/158
[10]: https://www.twilio.com/docs/usage/webhooks
[11]: https://developers.openai.com/api/docs/guides/rate-limits
[12]: https://owasp.org/API-Security/editions/2023/en/0x11-t10/
[13]: https://google.aip.dev/151
