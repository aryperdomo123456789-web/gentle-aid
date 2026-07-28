# Jobs longos — blindagem e auditoria

Documento de referência do motor de tarefas (`backend/app/services/jobs.py`) e
das correções aplicadas para que dublagem, recap, voz, transcrição, legendas e
esterilização terminem **sempre**, mesmo com deploy, restart ou queda de worker.

## 1. O problema original

O Gunicorn reciclava o worker por contagem de requisições (`max_requests`) no
meio de um job. Como o pipeline roda em thread dentro do processo web, o
`asyncio` do Edge TTS estourava:

```
cannot schedule new futures after interpreter shutdown
Autorestarting worker after current request
```

O job morria em silêncio e a Central de Jobs ficava presa em "processando"
para sempre.

## 2. O que foi corrigido

| Camada | Antes | Agora |
| --- | --- | --- |
| Execução | `ThreadPoolExecutor` (hooks `atexit` matam o job no shutdown) | Fila própria (`queue.Queue`) + threads daemon, sem `atexit` |
| Falhas | `except Exception` | `except BaseException` — pega também `SystemExit` do worker morrendo |
| Cancelamento | Evento em memória (só o worker que recebeu o request via) | Flag em disco `jobs/<id>.cancel` + evento — funciona entre processos |
| Sobrevivência | Nenhuma | `heartbeat_at`, `owner_pid`, `owner_host` gravados no JSON do job |
| Job órfão | Ficava "processando" eternamente | `reconcile_orphans()` no boot + cura na leitura (`get`/`list_jobs`) |
| Gravação | JSON reescrito a cada linha de FFmpeg | Gravação atômica (`.tmp` + `replace`) com throttle de 1s para log |
| Edge TTS | `asyncio.run` | Loop próprio criado/fechado na thread do job + 3 tentativas por bloco |
| Gunicorn | Reciclagem ativa | `max_requests = 0`, `timeout = 3600`, `graceful_timeout = 120`, hooks avisando o registro de jobs |

## 3. Como um job é considerado vivo

1. Toda tarefa em execução grava `heartbeat_at` a cada ciclo do batimento.
2. Ao ler o job, o sistema checa: o `owner_pid` ainda existe nesta máquina?
   O batimento é recente?
3. Se o dono morreu ou o batimento venceu, o job vira `error` com a mensagem
   "Job interrompido: o processo que executava a tarefa foi encerrado" — nunca
   fica travado no frontend.
4. No boot (`create_app`), `reconcile_orphans()` varre o disco e fecha tudo que
   ficou pendurado do processo anterior.

## 4. Cancelamento à prova de multi-worker

`request_cancel()` grava `jobs/<id>.cancel`. Qualquer worker que rode
`jobs.is_cancelled()` (cache de 1s para não martelar o disco) enxerga o pedido.
O `media.run()` — que executa **todo** FFmpeg do sistema — consulta esse estado
a cada 0,25s e mata o processo externo na hora.

## 5. Checkpoints por ferramenta

Loops longos verificam cancelamento entre etapas:

- `transcribe.py` — a cada bloco de áudio enviado ao provedor.
- `dubbing.py` — a cada lote de tradução e a cada trecho narrado.
- `edge_tts.py` — antes de cada bloco de narração.
- `recap.py`, `video_gen.py`, `delivery.py` — já possuíam checkpoints.
- Qualquer chamada de FFmpeg/ffprobe — via `media.run()`.

## 6. Timeouts obrigatórios

Nenhuma chamada externa pode prender um job para sempre:

- `media.run()` — teto de 4h, configurável por chamada.
- `ffprobe` (esterilizador) — 120s.
- Decodificação de áudio do beat sync — 600s.
- `fc-list` (fontes de legenda) — 20s.
- HTTP de imagens/vídeos (`visuals.py`) e provedores de IA — timeout explícito.

## 7. Operação no aaPanel

```bash
bash deploy/safe-update.sh          # atualiza código e reinicia com segurança
systemctl restart viral-api         # o boot reconcilia jobs órfãos sozinho
journalctl -u viral-api -f          # acompanhar
```

Após o restart, jobs interrompidos aparecem na Central de Jobs como falha
explícita com o rastro completo — basta reprocessar.

## 8. Limite conhecido (próximo passo)

Os jobs ainda rodam **dentro** do processo web. Isso já não corrompe estado nem
trava a interface, mas um deploy no meio de uma dublagem longa ainda cancela
aquela tarefa. A blindagem definitiva é o worker isolado (`viral-worker` via
systemd) consumindo a mesma fila persistente, com o web apenas enfileirando.
A estrutura atual (fila + flags em disco + heartbeat) já foi desenhada para
receber esse worker sem reescrever as ferramentas.
