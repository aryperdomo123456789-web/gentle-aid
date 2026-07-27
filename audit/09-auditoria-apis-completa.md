# 09 — Auditoria completa das APIs (chamada real, contrato e uso)

Objetivo: documentar **toda** chamada externa do Ecossistema Viral — método, URL,
cabeçalho de autenticação, corpo esperado, resposta esperada e qual ferramenta
quebra se a chave falhar. Serve como fonte única para trocar/substituir chaves
na Central de APIs (`/apis`) sem adivinhação.

Data da auditoria: revisão do repositório `gentle-aid` (branch de trabalho atual).

---

## 0. Correções aplicadas nesta auditoria

| Arquivo | Problema encontrado | Correção |
| --- | --- | --- |
| `backend/app/services/transcribe.py` | O polling do Whisper API usava `time.time()`, `time.sleep()` e `urllib.parse.quote()` **sem os imports** `time` e `urllib.parse`. Qualquer transcrição assíncrona pelo Whisper API estourava `NameError` e derrubava o fallback inteiro da Dublagem IA. | Adicionados `import time` e `import urllib.parse`. Fallback volta a funcionar. |

Confirmado como já correto (fix do Codex presente no código):

- `POST https://api.whisper-api.com/transcribe` autentica com **`X-API-Key`** (não Bearer).
- Todas as requisições de transcrição enviam `User-Agent: EcossistemaViral/1.0`.
- Groq permanece como **primeiro** provedor; Whisper API é fallback.

---

## 1. Regras gerais do cofre

- Chaves vivem em `fabrica_clips/_config/api_keys.json` (permissão `600`, fora do Git).
- Variáveis de ambiente sobrescrevem o JSON.
- **Nunca** ler `os.environ` direto: sempre `api_keys.get_key("<id>")`.
- A UI `/apis` executa a lista `test` de cada provedor em ordem; o primeiro
  candidato que responder `2xx` (e satisfizer `expect_json`, quando houver)
  marca a chave como válida.
- `401/403` = chave inválida/sem escopo. `402` = saldo. `429` = limite.

---

## 2. Transcrição (coração da Dublagem IA)

### 2.1 Groq — Whisper large v3 (primário)
- `POST https://api.groq.com/openai/v1/audio/transcriptions`
- Auth: `Authorization: Bearer gsk_...`
- Corpo: `multipart/form-data` com `file`, `model=whisper-large-v3`,
  `response_format=verbose_json`, `temperature=0`, opcional
  `timestamp_granularities[]=segment|word`, opcional `language`.
- Resposta: `{ language, text, segments:[{start,end,text,words?}] }`.
- Limites: upload ≤ 25 MB → o backend fatia o áudio em blocos de **600 s** e
  desloca os timestamps de cada bloco.
- Teste em `/apis`: envia um WAV real de 0,3 s (audio probe) — não apenas `/models`.
- Quebra: Dublagem IA, legendas automáticas, transcrição do Estúdio de Voz.

### 2.2 Whisper API (fallback)
- `POST https://api.whisper-api.com/transcribe`
- Auth: **`X-API-Key: <chave>`** + `User-Agent: EcossistemaViral/1.0`
- Corpo: multipart com `file`, `format=srt`, `model_size=large`, opcional `language`.
- Resposta síncrona: SRT (convertido em segmentos por `_payload_from_srt`).
- Resposta assíncrona: `{ task_id, status: queued|processing }` → polling em
  `GET {base}/status/{task_id}` (mesmo `X-API-Key`), timeout de 900 s.
- `WHISPER_API_BASE` apontando para outro host troca o modo para o contrato
  OpenAI (`{base}/audio/transcriptions`, Bearer, `model=whisper-1`).

---

## 3. Voz / TTS

### 3.1 ElevenLabs — `voice_engine.py`
- Base: `https://api.elevenlabs.io/v1`
- Auth: header `xi-api-key`.
- Speech-to-speech: `POST /speech-to-speech/{voice_id}` — multipart `audio`,
  `model_id=eleven_multilingual_sts_v2`. Preserva a narrativa e troca o timbre.
- Texto → fala: `POST /text-to-speech/{voice_id}` — JSON `{text, model_id: eleven_multilingual_v2, voice_settings}`.
- Chunking: fatias-alvo de 240 s (máx. 300 s) para latência e limite de payload.
- Testes em `/apis`: `GET /v1/user` e `GET /v1/voices`.
- `402` = créditos de voz esgotados (chave continua válida).
- Quebra: Estúdio de Voz, Voice Swap, Dublagem IA (etapa de síntese).

### 3.2 Edge TTS (`edge_tts.py`) + Voice Forge
- Sem chave: motor local/gratuito usado pelas vozes próprias e pelas personas
  "Chiclete Persuasivo" (assinaturas DSP aplicadas via FFmpeg).
- É o caminho que garante `dub_ready: true` mesmo sem ElevenLabs.

---

## 4. LLM (roteiro, ranking, tradução da dublagem)

Ordem de fallback em `dubbing.py` e `trends.py`:

| Provedor | Endpoint | Auth | Contrato |
| --- | --- | --- | --- |
| DeepSeek | `POST https://api.deepseek.com/chat/completions` | Bearer `sk-` | OpenAI chat |
| Groq | `POST https://api.groq.com/openai/v1/chat/completions` | Bearer `gsk_` | OpenAI chat |
| Mistral | `POST https://api.mistral.ai/v1/chat/completions` | Bearer | OpenAI chat |
| SiliconFlow | `POST https://api.siliconflow.com/v1/chat/completions` | Bearer `sk-` | OpenAI chat |
| OpenRouter | `GET https://openrouter.ai/api/v1/key` (teste) | Bearer `sk-or-` | roteador multi-modelo |
| Gemini | `GET https://generativelanguage.googleapis.com/v1beta/models` | header `x-goog-api-key` **ou** query `key` | chave começa com `AIza`; tokens `AQ.`/`ya29.` são OAuth e **não** funcionam |
| Cohere | `POST https://api.cohere.com/v1/check-api-key` | Bearer | resposta precisa trazer `valid: true`; chaves trial não acessam `/v1/models` |

Quebra: Radar Global (síntese de tendências), tradução/ajuste de fala na
Dublagem IA, geração de títulos e roteiros.

---

## 5. Pesquisa e extração (Radar Global / Descoberta)

| Provedor | Chamada | Auth | Corpo |
| --- | --- | --- | --- |
| Google Trends | `GET https://trends.google.com/trending/rss` e `.../trendingsearches/daily/rss` | nenhuma | RSS por país |
| Tavily | `POST https://api.tavily.com/search` | Bearer `tvly-` | `{query, max_results}` |
| Exa | `POST https://api.exa.ai/search` | header `x-api-key` | `{query, numResults}` |
| Firecrawl | `GET https://api.firecrawl.dev/v1/team/credit-usage` (teste) / `POST /v1/scrape` | Bearer `fc-` | `{url, formats}` |
| Jina Reader | `GET https://r.jina.ai/<url>` | Bearer `jina_` | markdown limpo |

Quebra: Radar Global e o painel de descoberta das ferramentas.

---

## 6. TikTok / redes

| Provedor | Chamada | Auth | Observação |
| --- | --- | --- | --- |
| TikAPI | `GET https://api.tikapi.io/public/check` e `/public/explore?country=br&count=1` | header `X-API-KEY` (fallback Bearer) | resposta precisa trazer `status: success`; 403 = plano expirado |
| Lamatok | `GET https://api.lamatok.com/v1/user/by/username?username=...` | query `access_key` ou header `x-access-key` | 402 = saldo zerado, chave válida |
| yt-dlp (`discovery.py`) | binário local, sem API | — | metadados, curtidas, comentários, legendas e preview antes de processar |

---

## 7. Infra e observabilidade

- **Cloudflare**: `GET /client/v4/user/tokens/verify` (Bearer, API Token `cfut_`).
  Global API Key legada exige `X-Auth-Key` + `X-Auth-Email` (`CLOUDFLARE_EMAIL`).
- **Langfuse**: `GET {LANGFUSE_HOST}/api/public/projects` com Basic auth
  `LANGFUSE_PUBLIC_KEY:LANGFUSE_SECRET_KEY`.
- **Hugging Face**: `GET https://huggingface.co/api/whoami-v2`, Bearer `hf_`
  (token tipo *Read*).

---

## 8. Laboratório de APIs (`/lab`, só no ambiente Lovable)

`src/lib/api-lab.presets.ts` reproduz **as mesmas chamadas acima** através do
servidor (sem CORS), incluindo o probe WAV de 0,3 s para transcrição. Use o Lab
para descobrir o retorno bruto real de uma chave nova **antes** de cadastrá-la
no aaPanel.

---

## 9. Matriz ferramenta → dependência

| Ferramenta | Depende de | Degradação sem a chave |
| --- | --- | --- |
| Dublagem IA | Groq/Whisper + ElevenLabs ou Voice Forge + FFmpeg | falha na etapa "Ouvindo áudio" |
| Voice Swap / Estúdio de Voz | ElevenLabs ou Edge TTS/Voice Forge | cai para vozes locais |
| Legendas virais | Groq/Whisper (transcrição) + FFmpeg/ASS | sem legenda automática, presets seguem funcionando |
| Radar Global | Google Trends (sem chave) + Tavily/Exa + LLM | perde ranking e previsão, mantém RSS |
| Descoberta / LinkInspector | yt-dlp | sem métricas e preview |
| Esterilização viral | FFmpeg local | independe de API |
| Jobs Center | interno | independe de API |

---

## 10. Checklist de validação no aaPanel

```bash
cd /www/wwwroot/gentle-aid
git pull
bash deploy/safe-update.sh
systemctl status viral-api --no-pager
curl -s http://127.0.0.1:8000/api/voice/catalog | head -c 400   # espere dub_ready: true
```

Depois, em `https://viral.vr766.com/apis`: clicar em **Testar** na Groq
(audio probe real), ElevenLabs e Whisper. Só considere pronto quando o log do
job mostrar `Ouvindo áudio` → `Transcrição via Groq · whisper-large-v3`.
