# Plano especialista: clonagem neural de voz por upload de áudio

Data: `2026-08-08`

## Objetivo

Criar uma ferramenta no **Ecossistema Viral** que permita ao operador:

1. enviar um áudio próprio de `1 a 10 minutos`;
2. gerar um **perfil neural de voz** novo e reutilizável;
3. digitar texto e transformar esse texto em áudio com a voz clonada;
4. tratar essa voz clonada como mais um perfil disponível no catálogo, ao lado
   das vozes já existentes no sistema.

O foco deste plano é sair do modelo atual de **persona acústica / timbre
forjado** e evoluir para uma **clonagem neural real**, com identidade de voz
mais fiel ao material de origem.

## Resposta curta

**Sim, tem como.**

Mas há uma diferença importante:

- o que existe hoje no código atual é uma combinação de TTS + filtros + perfis
  acústicos;
- a clonagem neural real exige um pipeline de captura, pré-processamento,
  validação, geração de embedding/voice profile e inferência com um motor que
  aceite clonagem por amostra;
- a qualidade final depende muito da limpeza do áudio, da duração, da língua,
  do ruído de fundo e do motor escolhido.

Ou seja: é viável, mas precisa ser desenhado como um produto próprio, não como
um simples ajuste no seletor atual de voz.

## Estado atual observado

### No aaPanel local (`/www/wwwroot/gentle-aid`)

O estado local já tem:

- o estúdio de voz com conversão, dublagem e TTS;
- o catálogo de vozes realistas;
- a camada `Voice Forge`, que cria perfis próprios como personas de áudio;
- o frontend já preparado para selecionar `forge`, `elevenlabs` e `local`;
- a navegação para a área `/voice-conversion`.

O que isso significa na prática:

- já existe a UI e o fluxo base para escolher voz;
- já existe persistência de perfis de voz;
- já existe preview e uso desses perfis em narração;
- ainda não existe, nesse snapshot local, um fluxo explícito de
  "suba um áudio meu e treine um clone neural dedicado".

### No `main` do GitHub

O `main` remoto evoluiu o estúdio de voz para um fluxo muito mais próximo do
que o produto precisa:

- tela mais clara de **Estúdio de Clonagem e Conversão de Voz**;
- painel `Voice Forge · Clonagem Ativa`;
- lista de personas próprias;
- seleção entre `Realista (ElevenLabs)`, `Minhas vozes (grátis)` e `Timbre local`;
- preview de voz, cadastro de persona e geração de variantes;
- integração com provider neural principal via ElevenLabs;
- validação de amostras, jobs assíncronos e persistência do catálogo.

Isso já aponta na direção certa de produto, mas ainda precisa ser fechado com
mais consistência, testes e separação clara entre neural real e fallback.

## Direção do produto

A ferramenta nova deve ter este contrato:

### Entrada

- upload de áudio do usuário;
- duração permitida entre `1` e `10` minutos;
- validação de qualidade antes de qualquer clonagem.

### Processamento

- limpeza do áudio;
- detecção de ruído, silêncio excessivo e cortes;
- transcrição para checagem de idioma e consistência;
- extração do perfil de voz;
- criação de um novo perfil clonado;
- versionamento do perfil.

### Saída

- novo item no catálogo de vozes;
- preview de fala;
- uso desse perfil em:
  - TTS com texto digitado;
  - dublagem;
  - conversão de mídia;
  - futuras automações do pipeline.

## Arquitetura recomendada

### 1. Camada de ingestão de áudio

Responsável por receber o arquivo e garantir que ele serve para clonagem.

Validações mínimas:

- extensão e codec suportados;
- duração entre 1 e 10 minutos;
- fala clara o suficiente;
- volume e SNR aceitáveis;
- sem música alta por cima;
- sem cortes abruptos;
- sem áudio duplicado ou eco exagerado.

Se o áudio falhar nessa etapa, o sistema deve devolver um diagnóstico
explicando o problema e sugerindo uma nova gravação.

### 2. Camada de normalização

Antes de clonar, o sistema deve:

- converter para sample rate padronizado;
- remover silêncio inútil;
- normalizar volume;
- reduzir ruído leve;
- separar trechos úteis de fala;
- marcar trechos descartados.

Essa etapa melhora muito a fidelidade do clone.

### 3. Camada de clonagem neural

Esta é a parte central.

O sistema precisa gerar uma representação persistente da voz, de preferência
com:

- `voice_profile_id`;
- metadados do sample original;
- idioma predominante;
- duração do material usado;
- qualidade do material;
- data de criação;
- versão do motor/modelo usado;
- status do perfil;
- opções de uso.

### 4. Camada de inferência

Depois de criado o perfil, o usuário deve conseguir:

- digitar um texto;
- escolher o perfil clonado;
- gerar um áudio novo;
- ouvir preview;
- baixar o resultado;
- reutilizar a voz em outros fluxos do app.

### 5. Camada de catálogo

A voz clonada precisa virar um item permanente no catálogo, igual às vozes que
já existem.

Ela deve aparecer como:

- nome amigável;
- origem do clone;
- idioma;
- duração do sample;
- status;
- data de criação;
- botão de preview;
- botão de uso em TTS;
- botão de arquivamento/remover.

## Modelo de dados sugerido

### `voice_profiles`

Campos principais:

- `id`
- `name`
- `type` (`neural_clone`, `forge`, `elevenlabs`, `local`)
- `source_audio_path`
- `source_audio_duration`
- `source_audio_language`
- `source_audio_quality`
- `engine`
- `engine_version`
- `profile_payload`
- `created_at`
- `updated_at`
- `status` (`processing`, `ready`, `failed`, `archived`)
- `notes`

### `voice_samples`

Campos principais:

- `id`
- `profile_id`
- `original_filename`
- `storage_path`
- `duration`
- `sample_rate`
- `channels`
- `snr_score`
- `transcript`
- `created_at`

### `voice_jobs`

Campos principais:

- `id`
- `profile_id`
- `kind` (`enroll`, `preview`, `tts`, `dub`)
- `status`
- `progress`
- `log`
- `error`
- `created_at`
- `finished_at`

## API sugerida

### Novo fluxo

- `POST /api/voice/enroll`
  - recebe o áudio bruto;
  - cria um job de clonagem;
  - devolve `job_id`.

- `GET /api/voice/enroll/<job_id>`
  - acompanha o progresso da clonagem.

- `GET /api/voice/profiles`
  - lista os perfis disponíveis.

- `POST /api/voice/profiles/<id>/preview`
  - gera prévia com texto curto.

- `POST /api/voice/tts`
  - usa o perfil clonado para sintetizar texto.

- `DELETE /api/voice/profiles/<id>`
  - arquiva ou remove o perfil.

## UX sugerida

### Tela 1: Criar voz

Fluxo em passos:

1. enviar áudio;
2. checar qualidade;
3. confirmar consentimento e finalidade;
4. gerar perfil;
5. ouvir preview;
6. salvar no catálogo.

### Tela 2: Catálogo de vozes

Cada voz deve mostrar:

- nome;
- tipo;
- origem;
- status;
- duração do sample;
- botão de testar;
- botão de usar no TTS;
- botão de editar nome;
- botão de arquivar.

### Tela 3: Texto para voz

O usuário escolhe:

- o perfil;
- o texto;
- o formato de saída;
- a velocidade;
- o estilo de entrega.

## Plano de implementação

### Fase 1: base funcional

- criar a página de upload da voz;
- criar a persistência de perfis;
- criar a fila de jobs;
- adicionar validação do áudio;
- registrar metadados do sample.

### Fase 2: clonagem neural

- integrar um motor de clonagem real;
- gerar embedding / profile;
- suportar preview com a voz clonada;
- expor o perfil no catálogo.

### Fase 3: uso produtivo

- permitir TTS com o novo perfil;
- permitir dublagem com a voz clonada;
- permitir troca entre perfis;
- permitir arquivamento e atualização.

### Fase 4: robustez

- reprocessamento automático;
- logs detalhados;
- retry de jobs;
- métricas de qualidade;
- monitoramento de falhas.

## Critérios de aceite

A feature só deve ser considerada pronta quando:

- o usuário enviar um áudio de 1 a 10 minutos;
- o sistema criar um perfil novo;
- o perfil aparecer no catálogo;
- o texto digitado gerar áudio com aquela voz;
- o preview soar consistente com o sample original;
- o job sobreviver a restart/reload sem perder estado;
- o sistema bloquear amostras ruins com mensagem clara.

## Riscos e cuidados

### Qualidade do áudio

Se a amostra vier com ruído, música, eco ou fala muito curta, o clone vai
piorar bastante.

### Limitações de motor

Nem todo motor que promete clonagem oferece fidelidade boa com poucos minutos
de áudio. O resultado pode variar muito.

### Segurança e consentimento

O sistema deve exigir que o operador confirme que o áudio enviado é próprio ou
tem autorização para uso.

### Privacidade

Arquivos originais e perfis clonados devem ficar fora do Git e só no storage do
servidor.

### Uso indevido

A ferramenta deve deixar claro que o uso é para a própria voz ou para vozes
autorizadas.

## Decisão técnica recomendada

Se a meta é **resultado mais fiel e mais rápido para produção**, o melhor
caminho é:

1. manter o estúdio atual como base de UI;
2. adicionar um fluxo novo de enrolamento de voz por áudio;
3. persistir perfis clonados como entidades reais do catálogo;
4. conectar esse fluxo a um motor neural que aceite clonagem por amostra;
5. usar o perfil clonado nos mesmos fluxos já existentes de TTS e dublagem.

## Próximo passo sugerido

Criar a primeira versão do fluxo com:

- upload do áudio;
- validação de duração e qualidade;
- criação do perfil;
- preview com a voz criada;
- uso do perfil no TTS.

Isso já entrega a experiência principal que você descreveu.
