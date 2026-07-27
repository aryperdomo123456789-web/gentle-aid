# Diagnostico da Central de APIs

## Hipoteses ordenadas por probabilidade

### 1) O boot do `viral-api` esta lento ou travando por causa do autofill automatico

O backend chama `api_keys.autofill_once()` durante a criacao da app. Esse fluxo varre varios caminhos, inclusive `/root`, antes de registrar as rotas. Se a arvore for grande ou houver filesystem lento, a API pode demorar a subir ou reiniciar em loop.

Referencias:

- `backend/app/__init__.py:33-37`
- `backend/app/services/api_keys.py:701-758`
- `backend/app/services/api_keys.py:979-1075`

Sinais esperados:

- `systemctl status viral-api` mostra restart repetido ou startup demorado
- `journalctl -u viral-api` mostra muitos acessos a arquivos ou pausa longa antes de "Serving"

### 2) O Nginx pode nao estar proxyando `/api/` para a porta certa

Se `location /api/` apontar para a porta errada, o frontend chama `/api/apis`, mas o backend real nunca recebe a requisicao.

Referencias:

- `deploy/nginx-site.conf.template:31-41`
- `deploy/nginx-locations.conf.template:1-18`

Sinais esperados:

- `curl -i https://viral.vr766.com/api/apis` devolve 502, 404 ou uma pagina do frontend, nao JSON da API
- `nginx -T` nao mostra o bloco esperado

### 3) `VIRAL_ROOT` ou `VIRAL_STORAGE` podem estar apontando para o diretorio legado

O codigo usa `VIRAL_ROOT` para derivar a raiz e `VIRAL_STORAGE` para o storage. Se o `.env` do systemd ainda estiver preso em `/www/wwwroot/viral.vr766.com`, o cofre vai para o lugar legado e a busca pode ler arquivos antigos ou errados.

Referencias:

- `backend/app/config.py:7-31`
- `deploy/viral-api.service.template:9-14`
- `deploy/viral-web.service.template:9-14`
- `backend/app/services/api_keys.py:939-975`

Sinais esperados:

- `systemctl show viral-api -p Environment`
- `cat /proc/<pid>/environ`
- `test -f /www/wwwroot/gentle-aid/.env` falha

### 4) O arquivo do cofre nao existe, esta vazio ou ficou com permissao errada

O cofre mora em `fabrica_clips/_config/api_keys.json` e e gravado com `0600`. Se a pasta nao existe, se o owner nao bate ou se o arquivo e inacessivel, a leitura pode retornar vazio ou falhar silenciosamente.

Referencias:

- `backend/app/services/api_keys.py:321-343`
- `backend/app/services/api_keys.py:389-408`
- `backend/app/services/api_keys.py:939-975`
- `src/routes/apis.tsx:405-406`

Sinais esperados:

- `ls -l /www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json`
- `stat` mostra owner diferente do usuario do service

### 5) O frontend esta saudavel, mas o timeout do cliente mascara o erro real

O cliente da pagina `/apis` aborta a chamada em 25 segundos. Se o backend estiver apenas lento, o usuario ve timeout em vez de um erro mais claro.

Referencias:

- `src/lib/api.ts:37-57`
- `src/routes/apis.tsx:107-116`

## Comandos de verificação

### 1. Status dos servicos

```bash
systemctl status viral-api viral-web
```

O que significa:

- `active (running)`: o processo esta de pe
- `failed` / `activating (auto-restart)`: ha crash ou startup travado
- `inactive`: o servico nao subiu

### 2. Logs da API

```bash
journalctl -u viral-api -n 200 --no-pager
```

O que significa:

- erros de importacao Python, permissao ou caminho errado aparecem aqui
- se houver pausas grandes antes do primeiro log, suspeite do `autofill_once`

### 3. Logs do frontend

```bash
journalctl -u viral-web -n 200 --no-pager
```

O que significa:

- se o Node nao sobe, a rota `/apis` pode abrir sem payload ou com erro de conexao

### 4. Teste local da API

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1:8000/api/apis
```

O que significa:

- `200` + JSON: Gunicorn e Flask estao vivos
- `404` em `/api/apis`: blueprint nao registrado ou app errada
- `500`: erro interno no backend
- timeout: boot travado, firewall local ou porta errada

### 5. Validacao via dominio

```bash
curl -i https://viral.vr766.com/api/apis
```

O que significa:

- `200` com JSON: Nginx proxy ok
- `502`: upstream morto ou porta errada
- HTML do frontend: `location /api/` nao esta sendo aplicado

### 6. Conferencia do Nginx

```bash
nginx -T | grep -A5 'location /api'
```

O que significa:

- o bloco deve mostrar `proxy_pass http://127.0.0.1:<porta>`
- se nao aparecer, o template nao foi aplicado no site certo do aaPanel

### 7. Verificacao do cofre

```bash
ls -l /www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json
stat /www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json
```

O que significa:

- owner deve ser o mesmo usuario dos servicos
- permissao ideal: `-rw-------`

### 8. Conferencia do `.env`

```bash
ls -l /www/wwwroot/gentle-aid/.env
grep -E '^(VIRAL_ROOT|VIRAL_STORAGE|VIRAL_FRONTEND|GUNICORN_BIND|SECRET_KEY)=' /www/wwwroot/gentle-aid/.env
```

O que significa:

- `VIRAL_ROOT` precisa apontar para `/www/wwwroot/gentle-aid`
- `VIRAL_STORAGE` precisa apontar para `/www/wwwroot/gentle-aid/fabrica_clips`

## Leitura rapida dos cenarios

- `curl local OK` e `curl dominio FAIL`: problema de Nginx
- `curl local FAIL` e `journalctl` mostra demora antes do boot: problema no autofill/scanner
- `curl local FAIL` e o log mostra path inexistente: problema de `VIRAL_ROOT` / `VIRAL_STORAGE`
- `curl local OK` mas `/apis` no navegador fica carregando: problema no frontend ou timeout de 25s

