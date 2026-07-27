# Checklist de Deploy

## Antes de mexer

```bash
cd /www/wwwroot/gentle-aid
git status --short
```

O que verificar:

- nao sobrescrever mudancas do usuario
- manter o branch atual coerente com o Lovable

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
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1:8000/api/apis
```

Esperado:

- `200 OK`
- JSON com `status: ok`
- JSON com `providers`

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

## Conferencia das variaveis

```bash
grep -E '^(VIRAL_ROOT|VIRAL_STORAGE|VIRAL_FRONTEND|GUNICORN_BIND|VIRAL_API_PORT)=' /www/wwwroot/gentle-aid/.env
```

Esperado:

- `VIRAL_ROOT=/www/wwwroot/gentle-aid`
- `VIRAL_STORAGE=/www/wwwroot/gentle-aid/fabrica_clips`

## Teste da tela

Abrir:

- `https://viral.vr766.com/apis`

Esperado:

- nao ficar preso em "Carregando..."
- mostrar lista de provedores
- permitir teste de conectividade

## Sinal verde final

- `viral-api` sobe sem atraso grande
- `/api/apis` responde rapido
- Nginx encaminha `/api/`
- o cofre existe no path atual
- nenhum arquivo sensivel foi versionado

