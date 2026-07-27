# Plano de Correcao para o Lovable

## Objetivo

Corrigir a Central de APIs sem mexer no comportamento de negocio alem do necessario, mantendo o cofre fora do Git e eliminando o risco de boot lento ou path legado.

## Ordem sugerida

### Etapa 1. Confirmar a raiz unica do deploy

Arquivo: `backend/app/config.py`

Mudanca sugerida:

- garantir que `VIRAL_ROOT` e `VIRAL_STORAGE` sejam a fonte unica da raiz e do storage
- evitar fallback silencioso para caminhos legados quando o deploy atual ja esta em `/www/wwwroot/gentle-aid`

Por que:

- evita gravar `api_keys.json` no lugar errado
- evita que o scanner leia o app velho por engano

### Etapa 2. Parar de varrer `/root` no boot

Arquivo: `backend/app/services/api_keys.py`

Funcao alvo:

- `_scan_roots()`
- `autofill_once()`

Mudanca sugerida:

- remover `/root` dos caminhos padrao
- reduzir os roots legados para os que realmente existem no servidor
- ou tornar o autofill um botao explicitamente acionado pela UI, nao um passo do boot

Por que:

- a varredura de filesystem no startup e a causa mais provavel de timeout
- o boot precisa ser previsivel para o Gunicorn subir rapido

### Etapa 3. Separar importacao automatica de persistencia

Arquivo: `backend/app/services/api_keys.py`

Funcoes alvo:

- `sync_env()`
- `autofill()`
- `set_key()`
- `delete_key()`

Mudanca sugerida:

- garantir que o cofre seja persistido apenas em `api_keys.json`
- evitar sobrescrever `.env` automaticamente, ou ao menos limitar isso a uma rotina de instalacao/admin
- se o `.env` continuar sendo espelho, documentar que ele e derivado e nao a fonte primaria

Por que:

- reduz conflito entre segredo versionado, segredo do servidor e segredo da interface
- evita que o deploy reescreva variaveis sensiveis sem controle

### Etapa 4. Tornar a Central resiliente quando o backend estiver lento

Arquivos:

- `src/lib/api.ts`
- `src/routes/apis.tsx`

Mudanca sugerida:

- melhorar a mensagem quando `apiGet("/api/apis")` estourar o timeout
- mostrar hint direto de `systemctl status viral-api` e `journalctl -u viral-api`
- se possivel, carregar a lista com estado vazio e erro inline em vez de travar a tela inteira em "Carregando..."

Por que:

- o usuario hoje fica sem contexto
- o erro de timeout nao diz se o problema e rede, Nginx ou boot lento

### Etapa 5. Ajustar o import automatico para nao confundir chave errada com chave boa

Arquivo: `backend/app/services/api_keys.py`

Funcoes alvo:

- `_harvest()`
- `_harvest_signatures()`
- `_parse_legacy_catalog()`
- `autofill()`

Mudanca sugerida:

- validar melhor quais entradas sao realmente credenciais e quais sao placeholders
- impedir que exemplos da documentacao entrem como chave real
- manter a regra de prefixo, mas com mensagens mais explicitas para Gemini, Cloudflare e Hugging Face

Por que:

- evita importar lixo do legado
- reduz falsos positivos no cofre

### Etapa 6. Endurecer a escrita no disco

Arquivo: `backend/app/services/api_keys.py`

Funcoes alvo:

- `_store_file()`
- `_save()`
- `sync_env()`

Mudanca sugerida:

- garantir criacao atomica do arquivo
- verificar owner/permissao depois de salvar
- registrar erro claro se o filesystem nao aceitar `0600`

Por que:

- o cofre nao pode falhar silenciosamente

### Etapa 7. Garantir que o Nginx aponte para a porta certa

Arquivos:

- `deploy/nginx-site.conf.template`
- `deploy/nginx-locations.conf.template`

Mudanca sugerida:

- revisar o valor real de `__API_PORT__` e `__WEB_PORT__`
- confirmar que o site do aaPanel recebeu o bloco correto

Por que:

- a UI chama `/api/apis`; se o proxy estiver errado, a tela nunca vai carregar o cofre

## Passo a passo operacional

1. Ajustar `backend/app/services/api_keys.py` para parar de varrer `/root` no boot.
2. Subir o backend e confirmar que `curl -i http://127.0.0.1:8000/api/apis` responde em poucos segundos.
3. Confirmar que o cofre existe em `/www/wwwroot/gentle-aid/fabrica_clips/_config/api_keys.json`.
4. Confirmar que `nginx -T` mostra `location /api/` apontando para a porta do Gunicorn.
5. Abrir `/apis` e validar que a lista vem sem depender de autofill pesado.
6. Se o cofre ainda vier vazio, executar o import manual pela UI e revisar os roots de busca.

## Resultado esperado

- `/api/apis` responde rapido e consistente
- a Central de APIs deixa de depender de scan pesado no boot
- as chaves ficam no servidor, fora do Git
- o legado nao sobrescreve o ambiente atual

