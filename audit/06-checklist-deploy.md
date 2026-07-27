# Checklist de Deploy

## Antes de mexer

```bash
cd /www/wwwroot/gentle-aid
git status --short
```

O que verificar:

- nao sobrescrever mudancas do usuario
- manter o branch atual coerente com o Lovable
- nao mexer em arquivos sensiveis sem backup do cofre

## Validacao de servicos

```bash
systemctl status viral-api viral-web
```

Esperado:

- ambos `active (running)`

## Logs de subida

```bash
journalctl -u viral-api -n 120 --no-pager
journalctl -u viral-web -n 120 --no-pager
```

Esperado:

- sem loops de restart
- sem `FileNotFoundError` para `.env`, `api_keys.json` ou `frontend_dist`

## Health check local

```bash
curl -i http://127.0.0.1:8010/api/health
curl -i http://127.0.0.1:8010/api/apis
```

Esperado:

- `200 OK`
- JSON com `status: ok`
- JSON com `providers`
- `api/voice/catalog` tambem responde com `dub_ready`

## Validacao pelo dominio

```bash
curl -i https://viral.vr766.com/api/health
curl -i https://viral.vr766.com/api/apis
```

Esperado:

- `200 OK`
- sem HTML do frontend no lugar da API

## Conferencia do proxy

```bash
nginx -T | grep -A5 'location /api'
```

Esperado:

- `proxy_pass http://127.0.0.1:<porta-do-gunicorn>`

## Conferencia do caminho do cofre

```bash
ls -l /www/wwwroot/gentle-aid/.env
ls -l /www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json
stat /www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json
```

Esperado:

- `0600`
- owner correto
- arquivo presente
- chaves lidas por `api_keys.get_key(...)`, nao direto por `os.environ`

## Conferencia das variaveis

```bash
grep -E '^(VIRAL_ROOT|VIRAL_STORAGE|VIRAL_FRONTEND|GUNICORN_BIND|VIRAL_API_PORT)=' /www/wwwroot/gentle-aid/.env
```

Esperado:

- `VIRAL_ROOT=/www/wwwroot/gentle-aid`
- `VIRAL_STORAGE=/www/wwwroot/gentle-aid/fabrica_clips`
- `VIRAL_API_PORT=8010` ou valor equivalente usado pelo Gunicorn

## Atualizacao segura

```bash
cd /www/wwwroot/gentle-aid && bash deploy/safe-update.sh
```

O que esse comando faz:

- verifica se ha alteracoes locais nao commitadas
- faz backup do `.env`
- puxa o estado mais recente da branch remota configurada
- restaura o `.env`
- executa `deploy/update.sh`
- sincroniza o catalogo de vozes e o estúdio de legendas

Se o deploy parar em erro:

- confira `journalctl -u viral-api -n 120 --no-pager`
- confira `journalctl -u viral-web -n 120 --no-pager`
- confirme `curl -s http://127.0.0.1:8010/api/health`

## Teste da tela

Abrir:

- `https://viral.vr766.com/apis`

Esperado:

- nao ficar preso em "Carregando..."
- mostrar lista de provedores
- permitir teste de conectividade
- o botão "Testar todas" precisa validar as chaves reais no servidor
- Groq e Whisper precisam responder antes de liberar a Dublagem IA

## Sinal verde final

- `viral-api` sobe sem atraso grande
- `/api/apis` responde rapido
- Nginx encaminha `/api/`
- o cofre existe no path atual
- nenhum arquivo sensivel foi versionado
- `curl -s http://127.0.0.1:8010/api/voice/catalog | head -c 400` mostra `dub_ready: true`
