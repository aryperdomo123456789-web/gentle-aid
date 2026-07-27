# Plano de Produção - Ferramenta de Voz

Data: 2026-07-27

## Objetivo

Levar a ferramenta de voz do `Ecossistema Viral` para um nível realmente
profissional em produção, com processamento confiável de arquivos de 10 segundos
até 3 horas, logs vivos, cancelamento, histórico rastreável e saída estável para
uso diário.

## Estado atual

Hoje a ferramenta de voz já existe e funciona como um pipeline de conversão
V2V baseado em FFmpeg.

O que ela faz agora:

- Aceita upload de áudio.
- Aceita URL quando a origem é suportada.
- Processa em job assíncrono.
- Gera logs em tempo real.
- Salva o histórico do job no disco.
- Permite cancelamento e exclusão.
- Aplica mutação de áudio com filtros de pitch, tempo, equalização e normalização.
- Entrega o arquivo final com limpeza estrutural e relatório auditável.

O que ela ainda não faz de forma completa:

- Não faz transcrição automática do áudio.
- Não separa locutor, música e ruído de forma inteligente.
- Não faz clonagem real de voz por IA.
- Não escolhe automaticamente a melhor estratégia por conteúdo.
- Não tem chunking/resume robusto para arquivos muito longos.
- Não tem fallback de modelo de voz nem fila dedicada por prioridade.

## Diagnóstico técnico

Pontos positivos do código atual:

- O job roda fora da request e não bloqueia o frontend.
- Existe persistência em JSON por job.
- O backend já suporta cancelamento.
- O motor de mídia tem timeout longo para arquivos grandes.
- A saída final já passa por esterilização.

Pontos de atenção:

- O catálogo da voz referencia `LEVELS` no endpoint de catálogo, mas o arquivo
  da rota não importa essa constante.
- O campo `preserve_timing` é recebido na interface, mas hoje não muda o fluxo
  real de processamento.
- O pipeline atual é de transformação acústica, não de voz IA completa.
- Para vídeo e áudio muito longos, um único bloco de processamento ainda é o
  caminho mais frágil.

## O que falta para ficar profissional de verdade

### 1. Camada de inteligência de áudio

Antes de converter, o sistema precisa entender o arquivo:

- Detectar fala, silêncio, música e ruído.
- Separar trilhas quando houver mais de um locutor.
- Identificar idioma.
- Medir duração real, pico, LUFS e faixa dinâmica.
- Classificar se o conteúdo é fala limpa, podcast, narração, vídeo externo ou
  áudio misto.

### 2. Pipeline de voz IA

Para ser uma ferramenta de voz realmente forte, o fluxo ideal é:

1. Ingestão do arquivo.
2. Análise técnica.
3. Segmentação por trechos.
4. Transcrição ou reconhecimento de conteúdo falado.
5. Escolha do perfil de voz.
6. Conversão por modelo de voz.
7. Pós-processamento de áudio.
8. Reencaixe no vídeo ou exportação de áudio.
9. Esterilização final.
10. Entrega e arquivamento do job.

### 3. Processamento robusto para arquivos grandes

Para arquivos de até 3 horas, o sistema precisa de:

- Chunking por segmento.
- Checkpoint por etapa.
- Retomada após falha.
- Retry por parte quebrada, e não do arquivo inteiro.
- Controle de memória e de CPU por job.
- Fila com prioridade e limite por usuário.

### 4. Vozes profissionais

Se o objetivo é produzir vozes realmente boas, o sistema precisa de:

- Presets de voz com nomes claros.
- Opção de voz masculina, feminina, narrador, comercial e social.
- Ajuste de velocidade, timbre, brilho, ambiência e ruído.
- Tratamento separado para voz limpa e voz com música de fundo.
- Exportação em formatos úteis: `wav`, `mp3`, `aac` e, quando preciso, trilha
  embutida no vídeo.

### 5. Operação em produção

O ambiente de produção precisa garantir:

- Worker estável.
- Logs em tempo real.
- Histórico por usuário.
- Cancelamento real.
- Exclusão real dos arquivos e registros.
- Timeout configurado por duração do arquivo.
- Monitoramento do status do job.
- Espaço suficiente em disco para jobs longos.

## Arquitetura recomendada

### Camada 1: Entrada

- Upload local.
- URL remota.
- Detecção de formato e validação.

### Camada 2: Análise

- `ffprobe` para metadados.
- Detecção de orientação, duração e codec.
- VAD para fala/silêncio.
- Classificação do conteúdo.

### Camada 3: Transformação

- Motor de voz IA ou V2V.
- Filtros de limpeza e normalização.
- Processamento por blocos.
- Reencaixe final com áudio consistente.

### Camada 4: Saída

- Arquivo final.
- Relatório técnico.
- Hash.
- Histórico.
- Link para assistir quando houver vídeo.

## Plano de produção por fases

### Fase 1 - Estabilização

Entregar produção com o que já existe:

- Corrigir bugs de importação e catálogo.
- Garantir que o job de voz não quebre em arquivos comuns.
- Manter logs vivos e cancelamento funcionando.
- Validar exportação de áudio.

### Fase 2 - Inteligência de áudio

- Adicionar análise de fala.
- Adicionar detecção de ruído e música.
- Adicionar classificação do tipo de conteúdo.
- Decidir automaticamente o melhor caminho de conversão.

### Fase 3 - Voz IA profissional

- Conectar motor de voz de verdade.
- Criar perfis de voz consistentes.
- Permitir seleção por caso de uso.
- Melhorar qualidade final.

### Fase 4 - Arquivos longos

- Quebrar em blocos.
- Processar em paralelo controlado.
- Reunir ao final.
- Retomar jobs interrompidos.

### Fase 5 - Acabamento de produção

- Monitoramento.
- Alertas.
- Métricas de desempenho.
- Limite de concorrência por conta.
- UX mais clara para áudio e vídeo.

## Critérios de aceite

A ferramenta de voz só deve ser considerada pronta para produção quando:

- Aceitar áudio curto e longo sem travar.
- Processar e exportar sem perder o job no F5.
- Permitir cancelar e apagar com efeito real.
- Gravar histórico por usuário.
- Mostrar logs vivos durante o processamento.
- Preservar ou alterar o timing conforme o modo escolhido.
- Entregar voz com qualidade consistente.
- Ter comportamento previsível em produção.

## Riscos atuais

- O pipeline atual pode parecer “profissional” na interface, mas ainda não é
  uma solução completa de voz IA.
- Arquivos muito longos podem pesar em CPU e disco.
- Sem chunking, qualquer falha grande pode obrigar reprocessamento total.
- Se o objetivo for clonagem de voz, será preciso integrar um modelo dedicado
  ou um serviço externo.

## Próximas ações recomendadas

1. Corrigir o bug do catálogo da voz e revisar o fluxo atual.
2. Definir se a prioridade é:
   - conversão timbral local com FFmpeg, ou
   - voz IA real com modelo dedicado.
3. Implementar análise de áudio antes da conversão.
4. Adicionar chunking e retomada por segmentos.
5. Criar perfis profissionais de voz e presets de exportação.

## Resumo executivo

A base atual já é boa para operação técnica, mas ainda está no meio do caminho
entre “processador de áudio” e “plataforma profissional de voz”.

Para virar um produto realmente forte, a próxima etapa é adicionar inteligência
de áudio, processamento por segmentos, perfis de voz melhores e um motor de voz
IA de verdade.
