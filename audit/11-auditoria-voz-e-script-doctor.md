# Auditoria 11 — Módulo de Voz + Doutor de Roteiro

Escopo: todas as ferramentas e funções de voz do Ecossistema Viral rodando no aaPanel
(`viral-api` na 8010, front na 3010). Data desta rodada: revisão completa dos 4 fluxos
de áudio + o novo chat de correção de roteiro por IA.

---

## 1. Mapa dos fluxos de voz

| Fluxo | Rota | Motor | Entrada | Saída |
|---|---|---|---|---|
| Trocar timbre | `POST /api/voice/convert` | `local` (FFmpeg), `forge` (DSP), `elevenlabs` (STS) | upload ou link | MP4 (mantém vídeo) ou MP3/WAV/AAC |
| Texto → narração | `POST /api/voice/tts` | `forge` (Edge TTS + persona), `elevenlabs` | roteiro até 500.000 chars | áudio esterilizado |
| Dublagem IA | `POST /api/voice/dub` | Whisper/Groq → tradução → TTS → mix | link YouTube/TikTok ou upload | MP4 dublado ou áudio |
| Doutor de Roteiro | `GET /script/styles`, `POST /script/analyze`, `POST /script/fix` | LLM (DeepSeek/Groq/Mistral) + fallback local | texto | texto reescrito + diagnóstico |

Todos criam job em `services/jobs.py` com `mode` no meta, então aparecem na Central de Jobs
com log, timeline, cancelar, apagar e download — mesmo padrão das outras ferramentas.

---

## 2. Falhas encontradas e corrigidas

### 2.1 Vazamento de arquivos temporários (crítico no aaPanel) — CORRIGIDO
Os workers apagavam os intermediários **só no caminho feliz**. Qualquer falha
(chave ElevenLabs inválida, vídeo sem áudio, provedor fora do ar, Whisper 401)
deixava no disco:

- `{job}_voice.wav` / `{job}_tts.wav` (narração bruta, pode ter centenas de MB)
- `{job}_muxed.mp4` / `{job}_dubmux.mp4`
- `{job}_dubtrack.wav` + `{job}_dubvoice.wav`
- o arquivo de origem baixado pelo yt-dlp

Em servidor de produção isso enche o disco em poucos dias de teste.

**Correção:** helper `_sweep(*paths)` em `backend/app/blueprints/voice.py`, chamado em
`finally` nos três workers (`_work_convert`, `_work_tts`, `_work_dub`) e também nos
`except` de síntese/STS/dublagem. `_sweep` engole `OSError` para nunca derrubar o job.

### 2.2 Erros de provedor sem rastro no job
`VoiceEngineError`, `EdgeTTSError` e `TranscribeError` já são convertidos em
`RuntimeError` com a mensagem original, que o `jobs.fail` grava no log — mantido.
Regra a preservar: **nunca** trocar essas mensagens por texto genérico; é por elas que
se descobre chave vencida vs. cota estourada.

### 2.3 Validação de entrada — OK, sem mudança
- `speed` limitado a 0.7–1.2 (fora disso o `atempo` distorce).
- `keep_ambience` limitado a 0.0–0.6 (acima disso o áudio original abafa a dublagem).
- `mutation`, `format`, `timing`, `target_lang` validados contra dicionário fechado.
- Upload validado por extensão (`MEDIA_EXT`) em `save_upload`.

### 2.4 Textos longos — OK
`edge_tts.split_text` quebra por frase respeitando `TEXT_CHUNK` e concatena os blocos,
então roteiro de 500k caracteres não estoura o limite do provedor. O ElevenLabs é
chunkado dentro de `voice_engine`.

---

## 3. Doutor de Roteiro (novo)

`backend/app/services/script_doctor.py`.

### 3.1 Ordem obrigatória do pipeline
`clean_for_speech` → `analyze` → (opcional) reescrita LLM → `analyze` de novo.
A limpeza **precisa** vir antes da análise, senão a contagem de palavras/segundos sai
errada e o tempo estimado de narração mente.

- Taxa de locução usada para PT-BR curto: **2.6 palavras/segundo**.
- Limpeza determinística: siglas por extenso, `!!!`/`???` colapsados, muletas removidas
  com recapitalização da frase, quebras de respiração.

### 3.2 Estilos narrativos (14)
Terror, Notícia/Jornalístico, True Crime, Documentário, Curiosidades, Storytime,
Motivacional, VSL/Vendas, ASMR, Comédia, Reflexivo, Tutorial, Esportivo, Mistério.

Cada estilo carrega `velocidade` e `expressividade` sugeridas — o front aplica
automaticamente no formulário quando o usuário escolhe o estilo (ex.: Terror → 0.9x /
dramática; Notícia → 1.1x / neutra).

### 3.3 Fallback sem IA
Se nenhuma chave de LLM estiver cadastrada em `/apis`, o endpoint `/fix` devolve
`fallback: true` e aplica só a correção local determinística. **Nunca** retorna erro —
a ferramenta continua utilizável offline.

---

## 4. Contratos do frontend

`src/features/voice/api.ts`
- `fetchScriptStyles(): ScriptStylesResponse`
- `analyzeScript(text): { analysis }`
- `fixScript({ text, style, action, instruction?, seconds? }): ScriptFixResult`

Tipos em `src/features/voice/types.ts`. O componente `ScriptDoctorChat.tsx` fica acima do
campo de roteiro em `TextToSpeechForm.tsx`, com undo do texto anterior antes de gerar o áudio.

---

## 5. Checklist de regressão no aaPanel

1. `/voice-conversion` → aba Texto → escolher estilo Terror → "Corrigir" → texto volta reescrito e a velocidade muda para 0.9x.
2. Sem chave de LLM: o chat responde com "Correção local" e não quebra.
3. Gerar narração com voz Forge → job aparece na Central com log de blocos do Edge TTS.
4. Forçar erro (chave ElevenLabs inválida) → job falha **e** `ls` na pasta de trabalho não deixa `*_tts.wav` órfão.
5. Dublar link do TikTok → transcrição, tradução, mix e MP4 final; pasta de trabalho limpa depois.
6. Cancelar um job de dublagem no meio → sem processo FFmpeg zumbi e sem WAV órfão.
