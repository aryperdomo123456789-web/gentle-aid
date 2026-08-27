# Aplicação do AIP-151 ao gentle-aid

**Status:** proposta técnica para a evolução da Mago API v1
**Data:** 27 de agosto de 2026
**Escopo:** operações longas, jobs de transcrição e futuros pipelines de mídia
**Referências principais:** AIP-151, AIP-152, AIP-155, AIP-193, AIP-194 e AIP-216

## Resumo executivo

O gentle-aid já usa a ideia central do AIP-151: uma operação demorada não bloqueia a requisição inicial; o cliente recebe um identificador, consulta o estado e busca o resultado depois. O `POST /api/v1/transcriptions` responde `202`, cria um job, publica polling, cancelamento e entrega protegida. Portanto, a base conceitual está correta.

A lacuna está na forma e na durabilidade do recurso. Hoje o sistema expõe um objeto `job` próprio, com `status`, `progress`, `result_url` e `error`, mas não possui um envelope uniforme de operação com `name`, `done`, `metadata`, `response` e `error`. O worker ainda vive em threads do processo Gunicorn e o estado é persistido em arquivos JSON. Isso funciona para alpha controlada, mas não oferece a durabilidade, a observabilidade e a previsibilidade necessárias para uma API de alto volume.

A recomendação é **não reescrever o sistema inteiro agora**. Devemos fazer uma evolução aditiva: preservar os campos atuais, acrescentar semântica compatível com operações longas, endurecer estados e erros, e só depois trocar o backend de fila por um worker persistente. Assim aceleramos a compatibilidade da API sem colocar uma migração de infraestrutura no caminho crítico.

> **Decisão recomendada:** adotar a semântica do AIP-151 como contrato público, mas manter JSON/HTTP próprio em `/api/v1`. O AIP-151 é orientado ao recurso `google.longrunning.Operation`; não devemos copiar protobuf ou fingir que o serviço é gRPC. Devemos preservar as propriedades que tornam o padrão útil: operação rastreável, resultado terminal, metadata de progresso, erro estruturado, cancelamento explícito e compatibilidade de tipos.

## O que o AIP-151 realmente exige

O AIP-151 recomenda que métodos que podem levar uma quantidade significativa de tempo retornem uma operação longa em vez da resposta final. A referência usa aproximadamente dez segundos como regra prática. A operação não deve ser streaming e precisa carregar informação suficiente para o cliente acompanhar o progresso e obter o resultado posterior [1].

O contrato de uma operação madura separa cinco conceitos: um nome estável para a operação, a indicação de terminalidade (`done`), metadata de progresso durante a execução, uma resposta de sucesso quando concluída e um erro estruturado quando falha. Erros que impedem o início devem voltar imediatamente; erros durante a execução pertencem ao recurso da operação [1] [3].

O AIP-151 também trata compatibilidade como parte do contrato: mudar os tipos de resposta ou metadata é uma alteração incompatível. A operação pode expirar depois de concluída, e uma política explícita de concorrência deve existir. Para o nosso caso, isso significa que o cliente nunca deve depender de detalhes internos como caminho físico, nome do provider ou formato do JSON de storage.

## Comparação com a implementação atual

| Semântica de operação longa | Estado atual do gentle-aid | Avaliação |
|---|---|---|
| Resposta assíncrona | `202 Accepted` no POST | Implementado |
| Identificador estável | `job_id` e `Location` | Implementado; recomendamos expor também `name` |
| Estado não terminal | `queued` e `running` internamente; `status` público | Implementado parcialmente |
| Terminalidade explícita | `terminal` interno; ausência de `done` no contrato público | Lacuna aditiva |
| Progresso | `progress`, `stage` e eventos | Implementado; falta envelope `metadata` |
| Sucesso terminal | `result_url` e download protegido | Implementado |
| Erro terminal | `error` público no job | Implementado parcialmente; mensagem pode carregar detalhe interno |
| Erro antes de iniciar | `Problem Details` HTTP | Implementado |
| Erro durante execução | job `failed` | Implementado; deve usar códigos estáveis e retryability |
| Cancelamento | `POST /jobs/{id}/cancel` | Implementado; pode evoluir para `:cancel` |
| Expiração | TTL lógico de 3 dias para resultado | Implementado; política deve ser publicada |
| Operação uniforme | Cada rota acessa diretamente o engine de jobs | Parcial |
| Persistência | JSON local + memória do processo | Adequado para alpha; não para escala |
| Durabilidade em restart | Reconciliação marca órfão como erro | Mitigação; não há retomada |
| Concorrência | Pool de threads por worker Gunicorn | Limitada e não compartilhada entre processos |
| Paginação | `page_token` ainda retorna 501 | Pendente |

## Mapeamento recomendado para a API v1

O campo `job_id` atual deve continuar existindo para compatibilidade, mas o recurso público deve ganhar um nome canônico de operação. Um exemplo de resposta de aceitação é:

```json
{
  "name": "operations/api-transcription-abc123",
  "id": "api-transcription-abc123",
  "object": "operation",
  "type": "transcription",
  "done": false,
  "status": "PENDING",
  "metadata": {
    "progress": 0,
    "stage": "accepted",
    "created_at": "2026-08-27T21:00:00Z",
    "expires_at": "2026-08-30T21:00:00Z"
  },
  "response": null,
  "error": null,
  "poll_url": "https://viral.vr766.com/api/v1/operations/operations%2Fapi-transcription-abc123"
}
```

Quando concluída, a mesma operação deve manter `name` e trocar apenas a parte terminal:

```json
{
  "name": "operations/api-transcription-abc123",
  "id": "api-transcription-abc123",
  "object": "operation",
  "type": "transcription",
  "done": true,
  "status": "SUCCEEDED",
  "metadata": {
    "progress": 100,
    "stage": "completed",
    "created_at": "2026-08-27T21:00:00Z",
    "finished_at": "2026-08-27T21:01:08Z"
  },
  "response": {
    "format": "vtt",
    "language": "pt",
    "result_url": "https://viral.vr766.com/api/v1/jobs/api-transcription-abc123/result"
  },
  "error": null
}
```

Em caso de falha durante a execução, `done` deve ser `true`, o estado deve ser `FAILED` e `error` deve conter código estável, mensagem acionável e indicação de retry. O servidor não deve devolver stack trace, caminho local, token, prompt, nome secreto de provider ou exceção bruta. O formato de erro deve seguir o envelope Problem Details atual e evoluir com uma seção `details` compatível com ErrorInfo [3].

## Melhorias que aceleram sem exigir uma grande migração

### 1. Adotar envelope de operação de forma aditiva

Adicionar `name`, `done`, `metadata`, `response` e `error` ao retorno de `POST /api/v1/transcriptions` e `GET /api/v1/jobs/{job_id}`. Os campos atuais (`id`, `status`, `progress`, `stage`, `poll_url` e `result_url`) permanecem durante a v1. Isso permite que novos consumidores adotem o padrão imediatamente sem quebrar o painel existente.

### 2. Padronizar estados públicos

O estado público deve ser pequeno e previsível: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` e `EXPIRED`. Os estados internos `queued`, `done` e `error` devem ficar escondidos atrás de um adaptador. O estado deve ser output-only e os clientes devem tolerar valores futuros, conforme a orientação do AIP-216 [6].

`EXPIRED` deve representar expiração lógica de resultado; `DELETED` deve representar remoção administrativa. Não devemos misturar os dois porque os consumidores precisam saber se devem tentar outro polling ou iniciar uma nova operação.

### 3. Separar erro de aceitação de erro de execução

O POST deve continuar devolvendo erro HTTP imediato para arquivo inválido, chave ausente, escopo insuficiente, payload incompatível, quota e falha ao enfileirar. Depois que o job for aceito, qualquer falha deve aparecer no recurso da operação com `done=true`, `status=FAILED` e código estável. Essa separação evita que clientes criem duplicatas quando o provider falhar depois da aceitação [1] [3].

### 4. Tornar a política de retry explícita

O cliente deve repetir o POST somente com o mesmo `Idempotency-Key`; em timeout de rede, deve consultar a operação antes de criar outra. Falhas `UNAVAILABLE` podem ser retryable com backoff e jitter. `INVALID_ARGUMENT`, `UNAUTHENTICATED`, `PERMISSION_DENIED`, `CANCELLED`, `DEADLINE_EXCEEDED` e `RESOURCE_EXHAUSTED` não devem ser repetidas automaticamente sem uma mudança de condição [5].

O worker pode repetir uma chamada transitória ao provider, mas precisa de limite de tentativas, deadline total, `Retry-After` quando aplicável e registro de tentativa em metadata. O retry do provider não pode gerar outro job público nem outra cobrança lógica.

### 5. Introduzir metadata útil, não telemetria vazada

A metadata pública deve conter somente progresso, etapa funcional, timestamps, tentativa atual e, no futuro, `estimated_completion_time` quando houver estimativa confiável. Não deve conter nome interno do host, PID, prompt, caminho físico, segredo ou mensagem bruta de exceção.

### 6. Criar um adaptador de operação

Em vez de cada blueprint montar seu próprio JSON, criar uma função única, por exemplo `operation_view(job, include_response=True)`, que faça a conversão de job interno para operação pública. Isso reduz divergência entre transcrição, legendas, voz e Studio e transforma a adoção futura do padrão em trabalho de configuração, não em cópia de código.

## Melhorias que exigem migração ou nova infraestrutura

| Mudança | Benefício | Dependência | Prioridade |
|---|---|---|---:|
| Tabela/coleção de operações durável | Polling consistente e histórico entre workers | Banco transacional | P0 |
| Broker e worker separado | Durabilidade, retry e escala horizontal | Redis/RQ, Celery ou equivalente | P0 |
| Outbox/event log | Evita job aceito sem evento e facilita auditoria | Banco + worker | P1 |
| Idempotência transacional | Reserva e criação atômicas | Mesma store da operação | P0 |
| Cleanup físico de artefatos | Reduz storage abandonado após TTL | Scheduler/worker de limpeza | P1 |
| Webhooks assinados | Evita polling intenso para consumidores | Endpoint de entrega + retries | P2 |
| Paginação por cursor | Histórico de jobs previsível | Cursor assinado e store | P1 |
| Quota e billing | Controle de custo por consumer | Métricas confiáveis | P1 |

## Gargalo principal do processo atual

O maior risco não é a ausência de um campo `done`; é a fila em threads dentro dos workers Gunicorn. Cada worker possui memória e fila próprias. Um restart pode interromper trabalho, e uma requisição encaminhada a outro worker pode não observar o mesmo estado em memória. A reconciliação em disco reduz o problema, mas converte a interrupção em falha; ela não retoma o processamento.

A sequência mais rápida e segura é manter a fila atual apenas para o alpha, mas colocar uma interface `JobExecutor` entre o blueprint e o worker. Primeiro testamos o contrato contra a interface; depois substituímos a implementação por um worker persistente sem reescrever os endpoints. O contrato público não deve conhecer se o executor é thread, processo ou broker.

## Ordem de implementação recomendada

| Fase | Entrega | Resultado verificável |
|---:|---|---|
| 1 | Adaptador `operation_view` e campos aditivos | POST e polling exibem semântica uniforme |
| 2 | Estados públicos e catálogo de erros | Consumidores conseguem programar sem ler detalhes internos |
| 3 | Testes de replay, falha, cancelamento e expiração | Contrato protegido contra regressão |
| 4 | Interface `JobExecutor` | Blueprint deixa de depender da fila concreta |
| 5 | Store durável de operações | Estado e idempotência deixam de depender de arquivos/memória |
| 6 | Worker separado com retry controlado | Restart não perde operações aceitas |
| 7 | Webhooks e paginação | Redução de polling e melhor integração externa |

## Ganhos esperados

A primeira fase melhora a integração imediatamente porque os consumidores passam a ter um contrato de operação uniforme, sem esperar pela troca de infraestrutura. A segunda reduz suporte e reprocessamento indevido por tornar estados e erros programáveis. A terceira cria uma fronteira de execução que permite acelerar a infraestrutura sem mudar a API pública. A quarta e a quinta removem o gargalo de durabilidade e habilitam escala real.

O que **não** deve ser feito agora é copiar literalmente o modelo protobuf, criar uma operação paralela para cada rota ou expor todos os estados internos. O valor do AIP-151 está na semântica e na uniformidade; a implementação HTTP/JSON deve continuar adequada ao produto e ao ecossistema atual.

## Critérios de aceite do próximo patch

O patch de evolução deve passar pelos seguintes critérios: a mesma operação conserva `name` do aceite ao resultado; `done` é falso enquanto `PENDING` ou `RUNNING` e verdadeiro em `SUCCEEDED`, `FAILED`, `CANCELLED` ou `EXPIRED`; o resultado não aparece antes da terminalidade; erro de execução não vira erro HTTP depois da aceitação; o retry com o mesmo `Idempotency-Key` não cria novo job; outro consumidor recebe `404`; `X-Request-Id` aparece em todas as respostas; `Retry-After` só aparece quando a resposta é retryable; e nenhum payload público contém path, PID, provider secreto ou stack trace.

## Referências

[1]: https://google.aip.dev/151 — Google AIP-151: Long-running operations.
[2]: https://google.aip.dev/152 — Google AIP-152: Jobs.
[3]: https://google.aip.dev/193 — Google AIP-193: Errors.
[4]: https://google.aip.dev/155 — Google AIP-155: Request identification.
[5]: https://google.aip.dev/194 — Google AIP-194: Automatic retry configuration.
[6]: https://google.aip.dev/216 — Google AIP-216: States.
