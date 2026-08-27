# P0 — Fila persistente, limites por consumidor e validação do provider

**Status:** implementação local validada; rollout de produção pendente de staging e de credencial válida para o teste real do provider.

## Objetivo

Os três bloqueios P0 da Mago API são tratados separadamente, mas compartilham o mesmo contrato de operação longa. A API web grava uma intenção serializável; o worker persistente executa fora do Gunicorn; o ledger por consumidor limita requests, jobs, segundos de áudio, custo estimado e concorrência; e o teste real comprova o caminho do provider com uma mídia curta e não pessoal.

## Fila persistente

A tabela `api_queue` vive no banco protegido do control plane e registra `job_id`, tipo, payload serializável, status, tentativas, disponibilidade, lease, worker e último erro. O endpoint HTTP não executa transcrição: ele grava o job e faz enqueue. O processo `backend/worker.py`, instalado como `viral-worker.service`, reivindica itens atomicamente, mantém lease por heartbeat, aplica retries limitados e finaliza o job.

O worker conhece somente tipos de tarefa permitidos. Para transcrição pública, o payload contém caminho interno temporário, idioma e formato; nenhum segredo, chave completa ou detalhe de provider entra no payload. Um retry temporário mantém a vaga de concorrência; sucesso, cancelamento e falha terminal liberam a vaga. A migração é explícita e o boot falha de forma observável se `api_queue` não existir.

## Limites e custo

O módulo `rate_limits.py` usa a tabela `api_usage_events`. Requests autenticadas são contadas por janela UTC de minuto. A criação de job reserva atomicamente job diário, segundos de áudio, unidades de custo estimado e uma vaga `active_job`. Se a fila falhar, as reservas são revertidas. O endpoint `/api/v1/usage` devolve contadores e limites somente da API key autenticada.

Os códigos públicos são `RATE_LIMIT_EXCEEDED`, `CONCURRENT_JOB_LIMIT_EXCEEDED`, `DAILY_JOB_QUOTA_EXCEEDED`, `DAILY_AUDIO_QUOTA_EXCEEDED` e `DAILY_COST_LIMIT_EXCEEDED`. O cliente recebe `Retry-After` em bloqueios retryable e headers de transparência como `X-RateLimit-Remaining` e `X-Quota-Jobs-Used`. `cost_units` é uma estimativa técnica e não uma fatura comercial.

Os defaults de alpha são configuráveis por ambiente: 60 requests por minuto, 100 jobs por dia, 3.600 segundos de áudio por dia, 3.600 unidades de custo por dia e 2 jobs concorrentes. Planos comerciais não devem reutilizar esses defaults sem uma política de billing e suporte.

## Provider real

O smoke test `provider_real_smoke.py` limita a mídia a oito segundos, usa o mesmo caminho `transcribe.transcribe()` do produto, não imprime transcrição nem segredo e remove os temporários. O caminho real foi alcançado, mas o Groq respondeu HTTP 401 `Invalid API Key`; por segurança, o teste parou sem fallback automático e sem repetir requests. A conclusão é que a integração de código está exercitada até a autenticação do provider, mas o aceite ponta a ponta permanece pendente da rotação da credencial no cofre.

## Testes

A suíte local possui quatro testes específicos de fila e limites e onze testes do contrato v1. Eles cobrem claim/lease/heartbeat/complete, retry e contagem de tentativa, rate limit, quota diária, idempotência, ownership, escopo, estados, cancelamento, expiração, erro sanitizado e OpenAPI.

O teste real com provider deve ser executado somente após a rotação de `GROQ_API_KEY` ou configuração de um provider de homologação. O teste deve usar uma mídia de referência aprovada, limite de duração, uma única tentativa e um teto de custo conhecido.

## Rollout

A sequência operacional é: executar migração explícita em backup, instalar/recarregar a unidade do worker, iniciar o worker, verificar `systemctl is-active viral-worker`, criar uma chave de teste com quota baixa, enviar uma mídia curta, consultar a operação e verificar o resultado protegido. Em qualquer falha, parar o worker, restaurar o backup e manter o Gunicorn legado íntegro.

A fila persistente não deve ser aplicada a jobs legados do painel sem uma fase de migração própria. Nesta etapa, o data plane público usa a fila persistente; o painel legado continua com o executor em processo até que seus fluxos tenham adapters e testes equivalentes.
