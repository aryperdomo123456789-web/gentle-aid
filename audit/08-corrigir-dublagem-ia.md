# Corrigir a Dublagem IA

Data: 2026-07-27

## O que quebrava

A Dublagem IA falhava na etapa de transcrição por dois motivos possíveis:

1. A chave da Groq podia responder `403` no `whisper-large-v3`.
2. O fallback Whisper estava usando o formato errado de chamada para a chave que estava no cofre.

No ambiente atual, a chave de `whisper` do cofre é do **Whisper API** e não de um endpoint OpenAI puro. O backend antigo tentava falar com `api.openai.com/v1/audio/transcriptions` usando `Bearer`, o que gerava `401 invalid_api_key`.

Além disso, a requisição sem `User-Agent` próprio podia ser barrada pelo Whisper API com `403 error 1010`:

- `browser_signature_banned`
- `The site owner has blocked access based on your browser's signature`

## Correção aplicada

O conector de transcrição foi ajustado para:

- testar **Groq** primeiro;
- cair para **Whisper API** quando houver chave do provedor `whisper`;
- usar `X-API-Key` no Whisper API;
- enviar `User-Agent: EcossistemaViral/1.0`;
- enviar `Accept: application/json`;
- buscar o Whisper API em `https://api.whisper-api.com/transcriptions`;
- manter compatibilidade com endpoint OpenAI-compatible quando `WHISPER_API_BASE` for definido explicitamente.

Arquivo principal corrigido:

- [backend/app/services/transcribe.py](/www/wwwroot/gentle-aid/backend/app/services/transcribe.py)

## Como validar

1. Reinicie a API:

```bash
systemctl restart viral-api
```

2. Confirme o catálogo:

```bash
curl -s http://127.0.0.1:8010/api/voice/catalog | head -c 400
```

3. Verifique se `dub_ready` está ativo.

4. Em `/apis`, rode o teste das chaves:

- Groq
- Whisper

5. Abra `/voice-conversion` → **Dublagem IA**.

6. Envie um vídeo ou use um job existente.

7. Confirme no rastro do job:

- `Transcrição via Groq · whisper-large-v3`
- `Whisper API` como fallback quando necessário
- `Dublagem X/Y trechos narrados`
- `Status: running → done`

## Prova de funcionamento

Foi validado um job real no servidor:

- `voice-51795cf8aeb2`

Resultado:

- transcrição passou;
- a dublagem avançou até o fim;
- o arquivo final foi entregue com sucesso;
- o job terminou em `done`.

## Sinais de erro e o que fazer

### `401 invalid_api_key`

Significa que a chave está errada, revogada ou apontando para o endpoint errado.

O que verificar:

- a chave existe em `/apis`;
- o provedor correto está configurado;
- `WHISPER_API_BASE` não está apontando para um endpoint incompatível;
- o token não é de outra conta.

### `403 error 1010`

No Whisper API, isso costuma ser bloqueio por assinatura/requisição do cliente.

O que verificar:

- `User-Agent` do backend;
- `Accept: application/json`;
- se a rota está indo para `https://api.whisper-api.com/transcriptions`;
- se a chave foi testada em `/apis`.

### `Groq 403`

Se a Groq recusar o áudio, o fallback precisa assumir.

O que verificar:

- a chave Groq está válida;
- a organização da Groq tem acesso à transcrição;
- o Whisper API está configurado e funcionando.

## Regra prática

Para a Dublagem IA funcionar de forma confiável:

1. Groq deve ser o primeiro teste.
2. Whisper API deve ser o fallback real.
3. O backend precisa usar um `User-Agent` próprio.
4. O job só pode prosseguir quando a transcrição gerar segmentos com timestamps.

