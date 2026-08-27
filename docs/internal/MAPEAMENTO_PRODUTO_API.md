# Mapeamento do produto autenticado e potencial de API

**Produto:** gentle-aid / Ecossistema Viral
**Domínio observado:** [`viral.vr766.com`](https://viral.vr766.com/)
**Data da exploração:** 27 de agosto de 2026
**Modo:** sessão autenticada, inspeção visual e leitura do código; nenhum job, teste de provedor, upload, live, geração, clonagem, criação de chave ou alteração administrativa foi disparado.
**Autor:** Manus AI
**Status:** Documento interno de produto e arquitetura; descreve capacidades observadas e recomendações de API. Não substitui o contrato público OpenAPI.

> **Conclusão executiva:** o gentle-aid não é apenas um painel de download. Ele já é uma plataforma de produção automatizada de mídia, com ingestão de URLs/uploads, descoberta, transcrição, transformação de áudio/vídeo, legendas, geração de roteiro, vídeo IA, recap, streaming, histórico e um cofre de integrações. O caminho correto é transformar esse motor em um **Media Production API**, mas sem expor diretamente as rotas legadas do painel.

## 1. O que foi observado no painel

A sessão autenticada exibiu uma navegação com quinze áreas operacionais: Desvio YouTube, Estúdio de Vídeo IA, Recap Narrado, Transcrição, Painel TikTok, Legendar, Voz V2V, Limpeza Canva, Live YouTube, Live TikTok, Radar Global, Central de Jobs, Central de APIs, Chaves de Acesso e Conta. O domínio carrega o mesmo ambiente auditado do gentle-aid, com a identidade Ecossistema Viral e a infraestrutura do aaPanel.

A superfície de produto pode ser entendida em cinco camadas:

| Camada | Papel | Estado atual |
|---|---|---|
| Painel de produção | Operação humana das ferramentas de mídia | Rico e já utilizável |
| Motor de jobs | Execução, progresso, logs, cancelamento, histórico e entrega | Implementado em threads + JSON |
| Central de APIs | Cofre e diagnóstico dos provedores do próprio produto | Implementado; 22 integrações visíveis |
| API Hub | Emissão, validade e revogação de chaves para consumidores | Implementado como control plane |
| API pública v1 | Consumo por outros projetos | Publicada para transcrição; ainda pequena frente ao painel |

A home do painel mostra o posicionamento atual: colar links de Shorts ou vídeos longos, escolher nicho, palavra-chave, intensidade e formato e iniciar uma esteira de download, recodificação H.264/AAC, remoção de metadados e micro-mutações. O painel também integra pesquisa viral e histórico do resultado.

## 2. Mapa funcional por aba

### 2.1 Desvio YouTube

A tela `/` é uma operação de lote para YouTube. O operador fornece um ou mais links, escolhe nicho, palavra-chave, nível de esterilização e formato final. A interface informa que o lote é processado fora da requisição e apresenta status, preview, detalhes, download e histórico.

| Elemento | Implementação |
|---|---|
| Endpoint principal | `POST /api/youtube/bypass` |
| Entrada | JSON com `urls`, `nicho`, `keyword`, `intensity`, `video_format`, `format_fit` e `source_card` opcional |
| Limite | Até 20 URLs por lote no backend |
| Pipeline | yt-dlp → FFmpeg → esterilização → entrega |
| Saída | Um ou mais vídeos, download, MD5 antes/depois, SHA-256, relatório e job |
| Dependências | yt-dlp, FFmpeg e origem pública acessível |
| API pública | Não expor a rota legada; criar recurso versionado de ingestão/normalização |

O valor de produto é a automação de uma esteira de transformação em lote. O risco é alto quando o módulo é descrito como “bypass” ou “clone” para conteúdo de terceiros. Para uma API comercial sustentável, a linguagem e o contrato devem ser de **ingestão e transformação de mídia autorizada**, com limites, aceite de responsabilidade e política de origem.

### 2.2 Estúdio de Vídeo IA

A tela `/estudio` transforma uma ideia em vídeo. O fluxo divide a tarefa em storyboard e execução: o operador escreve a ideia, escolhe estilo, duração e número de cenas, gera e revisa o storyboard, seleciona fonte visual, direção de arte, voz/persona, legendas, posição e trilha e só então inicia.

| Elemento | Implementação |
|---|---|
| Opções | `GET /api/studio/options` |
| Planejamento | `POST /api/studio/storyboard` |
| Execução | `POST /api/studio/run` |
| Modos visuais | Imagem IA grátis, B-roll real, mídia enviada e slot premium |
| Configurações | Aspecto 9:16/16:9/1:1, look, voz, persona, captions, música e mutação |
| Dependências | LLM para storyboard, Edge TTS, Pollinations e Pexels/Pixabay conforme o modo |
| API pública | Alta oportunidade, mas deve virar um recurso de projeto assíncrono com orçamento e quota |

O módulo resolve a criação de vídeo composto, não apenas a geração de uma imagem. O contrato futuro precisa modelar cenas como recursos editáveis, permitir revisão antes do render e registrar quais provedores foram usados.

### 2.3 Recap Narrado

A tela `/recap` recebe vídeo ou link público e oferece recap curto vertical ou longo horizontal. O operador define duração, estilo, engine de voz, persona, blocos de abertura/meio/fecho, ambiência, legenda, visão multimodal, formato e encaixe.

| Elemento | Implementação |
|---|---|
| Catálogo | `GET /api/recap/catalog` |
| Presets | `GET/POST/DELETE /api/recap/blocks` |
| Execução | `POST /api/recap/run` |
| Pipeline | Transcrição → visão de cenas opcional → brief → beats → narração → montagem → captions/esterilização |
| Saída | Recap 9:16 ou 16:9, beats, shots, transcript e relatório do job |
| Dependências | Transcrição, LLM, engine de voz e FFmpeg |
| API pública | Alta oportunidade, segunda onda; custo e direitos de conteúdo precisam estar claros |

O Recap é um dos módulos de maior valor percebido porque combina entendimento multimodal com produção final. É também um dos mais complexos e caros de operar. Não deve ser o primeiro endpoint público depois da transcrição.

### 2.4 Transcrição de vídeo

A tela `/transcrever` é simples: recebe um link público, cria um job e entrega um arquivo `.txt`. O código também implementa fallback para legendas automáticas do YouTube quando o download ou a transcrição por áudio falha.

| Elemento | Implementação |
|---|---|
| Endpoint do painel | `POST /api/transcribe/run` |
| API v1 equivalente | `POST /api/v1/transcriptions` |
| Entrada | URL pública; na v1, upload multipart |
| Saída | Texto, idioma detectado e job; v1 também oferece SRT, VTT e JSON |
| Dependências | yt-dlp, transcrição Groq/Whisper e legendas automáticas em fallback |
| API pública | **Primeiro produto API já publicado** |

Esse é o melhor núcleo de API porque possui entrada, processamento assíncrono, resultado e ownership definidos. A evolução natural é adicionar `source_url` à v1 com allowlist de origens e políticas SSRF, sem reutilizar cegamente a rota antiga.

### 2.5 Painel TikTok

A tela `/tiktok` expõe radar de tendências por nicho e região, além de clonagem por link direto. O operador escolhe intensidade e formato, revisa a origem e acompanha o histórico do clone.

| Elemento | Implementação |
|---|---|
| Radar | `GET /api/tiktok/trends` |
| Clonagem | `POST /api/tiktok/clone` |
| Entrada | Nicho/região ou URL, intensidade, formato e enquadramento |
| Saída | Cards de tendência, métricas de origem e vídeo recodificado |
| Dependências | TikAPI/Lamatok/yt-dlp, conforme o caminho |
| API pública | Média; antes, publicar `discovery` e `media/normalize` genéricos |

A API não deve prometer acesso garantido a uma plataforma que pode mudar autenticação, limites ou disponibilidade. O recurso deve ser vendido como análise de origem e transformação de mídia autorizada, não como garantia de captura de qualquer URL.

### 2.6 Estúdio de Legendas Virais

A tela `/legendar` é mais rica que o formulário simples da API legada: funciona como um editor visual, com Arquivo, Descartar, desfazer, refazer, Uploads, Pesquisar, Estilos, Texto, Animação, Cores, Esterilizar, Exportar, Job e Histórico. Ela aceita vídeo, oferece prévia de timeline e permite exportação legendada.

| Elemento | Implementação |
|---|---|
| Presets | `GET /api/legendar/presets` |
| Execução | `POST /api/legendar/run` |
| Entrada | Vídeo/URL, SRT ou texto, preset, posição, animação, cores, emoji, beat sync e formato |
| Saída | MP4, ASS e SRT; job com linhas, BPM/confiança e relatório |
| Dependências | FFmpeg; transcrição quando não há SRT/texto; detector de batida opcional |
| API pública | **Alta oportunidade após media upload/result** |

O produto resolve mais do que “adicionar legenda”: transforma texto em linhas temporizadas, pode sincronizar com batida e queima ASS em formatos sociais. A futura API deve tratar presets como recursos versionados e aceitar configuração declarativa, não reproduzir o estado visual do editor.

### 2.7 Estúdio de Voz

A tela `/voice-conversion` concentra quatro produtos: Trocar timbre, Dublagem IA, Texto → narração e Criar voz. A sessão observada informou que ElevenLabs não estava configurada, mas mostrou Voice Forge e vozes locais como fallback.

| Modo | Rota principal | O que resolve |
|---|---|---|
| Catálogo | `GET /api/voice/catalog` | Engines, vozes, personas, formatos, timing e readiness |
| Prévia | `POST /api/voice/preview` | Gera amostra curta síncrona |
| Script Doctor | `GET /api/voice/script/styles`, `POST /api/voice/script/analyze`, `POST /api/voice/script/fix` | Corrige, reescreve, melhora gancho, encurta, alonga e fecha com CTA |
| Personas | `GET/POST /api/voice/personas`, `DELETE`, `reset`, `clone`, `variants`, `bulk`, `preview` | Cria e administra vozes próprias; clonagem neural exige consentimento e ElevenLabs |
| Trocar timbre | `POST /api/voice/convert` | Troca narrador em áudio/vídeo por local, Forge ou ElevenLabs |
| Texto → narração | `POST /api/voice/tts` | Converte roteiro em áudio com velocidade e expressividade |
| Dublagem IA | `POST /api/voice/dub` | Transcreve, traduz quando necessário, sintetiza, mistura e entrega |

O backend documenta arquivos de 10 segundos a 3 horas, formatos MP4/MOV/MKV/WAV/MP3/M4A, timing estrito/natural, saída áudio/vídeo e idiomas de dublagem. O código estabelece limite de texto de 500.000 caracteres, mas o limite comercial deveria ser menor e baseado em quota/custo.

O maior cuidado de produto é semântico: Voice Forge/DSP é uma persona acústica sobre uma voz base; clonagem neural real é uma capacidade diferente. A API deve separar `voice_profiles` de `neural_voice_clones`, exigir consentimento, registrar origem e não usar a palavra “indetectável” como promessa técnica.

### 2.8 Limpeza pós-Canva

A tela `/canva-cleaner` recebe vídeo exportado MP4/MOV/WEBM, com limite visível de 500 MB, bitrate auto/4000/6000/8000 kbps, nível de esterilização, formato e encaixe. O endpoint `POST /api/canva-cleaner/run` recodifica H.264/AAC, remove metadados e devolve hash/relatório.

Esse é um ótimo candidato a API porque é determinístico, possui parâmetros claros e não precisa de LLM. A nomenclatura pública recomendada é `POST /api/v1/media/normalize` ou `POST /api/v1/media/transcode`, com descrição de limpeza de metadados e normalização de formato. Não expor “bypass” como promessa de contornar política de plataforma.

### 2.9 Live YouTube e Live TikTok

As telas `/live-youtube` e `/live-tiktok` usam o mesmo controlador. Ambas permitem selecionar vídeos do acervo ou fazer upload, definir preset, URL RTMP, stream key, overlays, reconexões e acompanhar saúde, bitrate, FPS, frames, descartados e reconexões.

| Elemento | Implementação |
|---|---|
| Opções | `GET /api/live/options` |
| Acervo | `GET /api/live/library` |
| Status | `GET /api/live/status` |
| Sessões | `GET /api/live/sessions` |
| Iniciar | `POST /api/live/start` |
| Parar | `POST /api/live/stop` |
| Limite | Playlist de até 20 vídeos; paths validados dentro do storage |
| API pública | Baixa prioridade; é control plane de streaming, não endpoint inicial |

Live tem potencial comercial, mas exige gestão de segredo RTMP, concorrência, reconexão, quota e responsabilidade operacional. Deve ser uma API separada de sessões, com stream keys referenciadas por secret ID, jamais devolvidas em respostas.

### 2.10 Radar Global

A tela `/radar` fica congelada até o operador clicar em Varrer radar. Ela oferece nicho, região, buscas em alta, vídeos com tração real, previsão de nichos, intensidade e formato para eventual transformação.

| Endpoint | Função |
|---|---|
| `GET /api/radar/global` | Radar por nicho/região com refresh opcional |
| `GET /api/radar/snapshot` | Último snapshot persistido |
| `GET /api/radar/forecast` | Previsão baseada nos dados disponíveis |
| `GET /api/radar/searches` | Buscas do Google Trends |

O radar deve virar API de dados com cache, timestamp, origem e nível de confiança. O contrato não deve apresentar previsão como certeza. Google Trends pode manter RSS sem chave; ranking e interpretação dependem de Exa/Tavily/LLM e devem aparecer como fontes/dependências do resultado.

### 2.11 Central de Jobs

A tela `/historico` é o centro operacional. Ela mostra atualização, filtros por ferramenta, filtros por estado, busca por ID/arquivo/origem, contadores, volume entregue, detalhes, download, cancelamento e exclusão.

No código, um job possui status `queued`, `running`, `done`, `error` ou `cancelled`, progresso, estágio, timestamps, eventos, log, outputs, artifacts, metadata, heartbeat, owner PID/host e duração. A persistência é feita em JSON por job; a auditoria global é append-only; a gravação usa arquivo temporário e `replace`; o cancelamento combina evento em memória e flag `.cancel` em disco.

O motor está blindado contra jobs órfãos, mas ainda opera dentro do processo web. Um restart pode interromper um job longo, após o qual a reconciliação o marca como falha explícita. Para API pública de alto volume, o próximo passo é um worker separado com fila persistente.

### 2.12 Central de APIs

A tela `/apis` é o cofre de integrações do produto. Após carregamento, ela mostrou 22 integrações mapeadas, 16/22 com chave ativa e 7 com falha no último teste. As categorias visíveis incluem LLM, Pesquisa Web, Transcrição/LLM, Banco de mídia, Extração, Infra, LLM/Modelos, Observabilidade, Rerank, TikTok, Transmissão ao vivo e Voz/TTS.

Os controles são Recarregar, Preencher automaticamente, Reparar as que falharam, Diagnóstico, Testar todas e acesso às Chaves de Acesso. Os cards exibem estado, origem, variável, último teste, documentação do provedor e campos de substituição. Valores de chave aparecem mascarados e não foram capturados.

Essa área é **control plane interno**. O consumidor da API pública não deve chamar `/api/apis`, receber lista de provedores ou editar o cofre global. A API pública deve expor apenas capacidades do produto e abstrair o provedor quando isso fizer sentido.

### 2.13 Chaves de Acesso

A tela `/api-hub/chaves` é a base de monetização e integração. O owner informa nome, validade e escopos, gera a chave e vê o valor completo uma única vez. Depois o sistema mantém hash/prefixo, validade, último uso e estado de revogação. A sessão observada tinha uma chave de teste revogada; não foi gerada outra.

O fluxo já sustenta a ideia de API para outros projetos, mas precisa evoluir para planos, quotas, uso por período, rotatividade, scopes definidos por produto e auditoria de consumidor. `api`, `public` e `saas` como texto livre não devem ser o contrato final; os escopos devem ser uma enumeração versionada e validada no servidor.

### 2.14 Conta

A tela `/conta` é o Console do dono. Ela permite trocar nome/senha da conta ativa e, para owner, filtrar, editar e remover contas. A sessão observada mostrou um owner protegido e um usuário operador.

Esse módulo deve permanecer separado da API pública. Consumidores externos precisam de API keys, não cookies de sessão humana. Operações de gestão de usuários, autenticação, cofre e revogação devem ficar em control plane administrativo.

## 3. Mapa de funções no código

A relação completa de funções e rotas está em [`MAPA_FUNCOES_GENTLE_AID.md`](./MAPA_FUNCOES_GENTLE_AID.md). O extrator AST encontrou 17 blueprints, 131 funções relacionadas a blueprints, 28 módulos de serviço, 434 funções de serviço e 16 rotas frontend. Os arquivos que formam o núcleo do produto são:

| Arquivo | Núcleo de responsabilidade |
|---|---|
| `backend/app/__init__.py` | Factory Flask, registro de blueprints, health, docs e handlers |
| `backend/app/config.py` | Storage, binários, limite de upload e workers |
| `backend/app/services/jobs.py` | Fila, ciclo de vida, heartbeat, cancelamento, auditoria e exclusão |
| `backend/app/services/delivery.py` | Entrega final, hashes, esterilização e relatório |
| `backend/app/services/validation.py` | Extensões, URLs, upload, paths e output |
| `backend/app/services/api_auth.py` | API key, escopo, request ID e Problem Details |
| `backend/app/services/idempotency.py` | Reserva, replay, conflito e persistência idempotente |
| `backend/app/blueprints/api_v1.py` | Data plane público atual de transcrição |
| `backend/app/services/api_keys.py` | Cofre de provedores externos |
| `backend/app/services/release_keys.py` | Emissão, hash, validade e revogação de chaves de consumidores |
| `backend/app/blueprints/voice.py` | Voz, Forge, TTS, conversão e dublagem |
| `backend/app/blueprints/legendar.py` | Legendas ASS/SRT, transcrição e beat sync |
| `backend/app/blueprints/recap.py` | Brief, visão, beats, narração e montagem |
| `backend/app/blueprints/studio.py` | Storyboard e geração de vídeo |
| `backend/app/blueprints/live.py` | Playlist e streaming RTMP |
| `backend/app/blueprints/discover.py` | Pesquisa e inspeção de links |
| `backend/app/blueprints/radar.py` | Radar, snapshot, previsão e buscas |

## 4. O que deve virar API primeiro

A prioridade foi calculada por clareza de contrato, repetibilidade, valor para integração, dependência externa e risco operacional. A nota não é estimativa de faturamento; é ordem de engenharia.

| Prioridade | Recurso público proposto | Fit API | Esforço | Risco | Decisão |
|---:|---|---:|---:|---:|---|
| 1 | `POST /api/v1/transcriptions` | 10 | 3 | Médio | Já publicado; tornar o slice robusto |
| 2 | `POST /api/v1/media/normalize` | 9 | 3 | Baixo/médio | Transformar Limpeza Canva em recurso genérico |
| 3 | `POST /api/v1/captions` | 9 | 5 | Médio | ASS/SRT/beat sync depois do upload/result |
| 4 | `POST /api/v1/speech` | 8 | 5 | Médio/alto | TTS com provider abstraction e quotas |
| 5 | `POST /api/v1/discovery/inspect` | 8 | 3 | Médio | Card de origem, métricas e fontes |
| 6 | `POST /api/v1/voice/conversions` | 8 | 7 | Alto | Só após consentimento, custo e worker dedicado |
| 7 | `POST /api/v1/dubbings` | 8 | 8 | Alto | Transcrição, tradução, síntese e mixagem |
| 8 | `POST /api/v1/recaps` | 7 | 9 | Alto | Produto premium após pipeline estável |
| 9 | `POST /api/v1/video-projects` | 7 | 9 | Alto | Projeto com cenas editáveis e orçamento |
| 10 | `POST /api/v1/radar/runs` | 7 | 6 | Médio | Cache, fontes e confiança obrigatórios |
| 11 | `POST /api/v1/streaming/sessions` | 5 | 9 | Muito alto | Deixar por último; segredo RTMP e operação 24/7 |

A sequência lógica é transformar primeiro as capacidades **determinísticas e de contrato claro** em API. Só depois devem entrar pipelines de múltiplos provedores, alto custo e responsabilidade operacional. Expor vinte rotas legadas de uma vez seria aquela clássica gambiarra com terno: parece produto até o primeiro retry.

## 5. Contrato comum para todas as futuras APIs

Cada recurso público deve seguir o mesmo protocolo: autenticação via API key, escopo específico, `Idempotency-Key` para criação, `X-Request-Id`, status 202 para processamento assíncrono, polling por recurso, ownership por consumidor, resultado protegido, TTL explícito, `Problem Details`, rate limit, usage e eventos auditáveis.

| Contrato | Regra recomendada |
|---|---|
| Identidade | API key nunca em URL; aceitar `X-API-Key` ou Bearer |
| Escopo | Enumeração fechada; nenhum texto livre autoriza privilégio |
| Criação | `202 Accepted` + `Location` + objeto de job |
| Idempotência | Mesmo payload reproduz resposta; payload diferente gera 409 |
| Ownership | `consumer_id` em cada job e artifact; outro consumidor recebe 404 |
| Resultado | Endpoint autenticado; nunca caminho físico ou alias público |
| Expiração | TTL por tipo de artefato e resposta 410 após expirar |
| Erro | `application/problem+json` com `code`, `detail`, `retryable` e request ID |
| Limites | Tamanho, duração, concorrência, quota e custo por plano |
| Webhook | Assinatura, retry com backoff, replay seguro e evento idempotente |
| Observabilidade | Latência, provider, custo estimado, bytes, estado e correlation ID |
| Compatibilidade | `/api/v1`; mudanças aditivas sem quebrar schema; depreciação comunicada |

## 6. Modelo de produto API

O painel deve continuar sendo a ferramenta de operação humana; a API deve ser a camada de automação para outros produtos. O posicionamento mais forte é oferecer **produção de mídia como infraestrutura**, não vender cada tela como endpoint isolado.

| Produto | Capacidades | Consumidor |
|---|---|---|
| Core Media API | Upload, transcrição, normalização, captions e resultados | SaaS, automações e equipes de conteúdo |
| Voice API | TTS, conversão, personas autorizadas e dublagem | Plataformas de conteúdo e educação |
| Creative Pipeline API | Storyboard, cenas, recap e render | Aplicações que precisam gerar vídeo |
| Intelligence API | Discovery, radar, snapshot, forecast e fontes | Ferramentas de pesquisa e planejamento |
| Live Control API | Sessões RTMP, playlist e saúde | Operações de transmissão 24/7 |

A monetização futura deve ser baseada em recursos consumidos — minutos de áudio, minutos de vídeo, bytes, jobs simultâneos e chamadas de LLM — e não em acesso irrestrito ao servidor. O painel de chaves já é a semente do control plane, mas ainda falta billing/quota real.

## 7. Bloqueios antes de expandir a API

O primeiro slice está publicado e protegido, mas ainda não é a plataforma final. Antes de abrir novos módulos para terceiros, é necessário trocar a fila em processo web por worker persistente, completar paginação por cursor, registrar usage real, aplicar rate limit por chave, retirar completamente o alias legado de outputs e criar testes de contrato por endpoint.

Também é necessário separar claramente dados do consumidor de dados do painel. A API pública não pode consultar o histórico global, o cofre de provedores, a biblioteca inteira do servidor ou arquivos de outra chave. O endpoint de resultado deve continuar validando path dentro do storage e entregando somente artefatos do próprio job.

## 8. Roadmap de execução

**Etapa 1 — Produto mínimo confiável.** Fortalecer transcrição v1 com upload/URL controlada, teste real, ownership cruzado, revogação, expiração, idempotência, usage e documentação live.

**Etapa 2 — Media Core.** Publicar normalização de mídia, captions e discovery inspect com os mesmos schemas, limites e jobs.

**Etapa 3 — Voz.** Publicar TTS antes de conversão e dublagem; separar Voice Forge de clonagem neural; exigir consentimento e criar governança de voice profiles.

**Etapa 4 — Pipelines compostos.** Publicar recap e Studio como projetos assíncronos com cenas, custos, provedores e checkpoints.

**Etapa 5 — Inteligência e streaming.** Publicar radar com fontes/confiança e Live como sessões protegidas somente depois de worker persistente e observabilidade operacional.

## 9. Estado da exploração

A exploração autenticada foi somente leitura. Foram abertas as abas do painel, inclusive submodos de Voz, e observados campos, instruções, dependências, históricos, estados e controles. Não foram realizados login adicional, upload, busca externa, geração de storyboard, preview, clonagem, dublagem, transcrição, teste de API, emissão/revogação de chave, alteração de conta, início de live ou exclusão de job.

## Referências internas

[1]: ../../backend/app/blueprints/api_v1.py — API pública v1 e ownership de jobs.
[2]: ../../backend/app/services/jobs.py — motor de jobs, fila, estados, heartbeat e auditoria.
[3]: ../../backend/app/services/delivery.py — entrega, hashes, artefatos e relatório técnico.
[4]: ../../backend/app/blueprints/voice.py — Voice Forge, TTS, conversão e dublagem.
[5]: ../../backend/app/blueprints/legendar.py — legendas, SRT/ASS e beat sync.
[6]: ../../backend/app/blueprints/recap.py — pipeline de recap.
[7]: ../../backend/app/blueprints/studio.py — storyboard e vídeo IA.
[8]: ../../backend/app/blueprints/live.py — sessões e streaming RTMP.
[9]: ../../backend/app/blueprints/transcribe_video.py — transcrição por URL e fallback de captions.
[10]: ../../backend/app/blueprints/release_keys.py — control plane de chaves de consumidores.
[11]: ../../backend/app/blueprints/apis.py — Central de APIs e cofre de provedores.
[12]: ../../audit/09-auditoria-apis-completa.md — matriz de provedores e degradações.
[13]: ./MAGO_API.md — memória interna da API pública e decisões de arquitetura.
[14]: ../public-api/README.md — guia público da API e status de pré-lançamento.
[15]: ../../audit/00-INDEX.md — índice dos documentos de auditoria e produção.
[16]: ./MAPA_FUNCOES_GENTLE_AID.md — inventário AST de funções e rotas.
