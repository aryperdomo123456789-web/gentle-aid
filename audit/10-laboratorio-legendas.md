# 10 — Laboratório local de Legendas (lógica certa da Ferramenta 3)

Rota: **`/lab-legenda`** · Código: `src/lib/caption-lab.ts` · Testes: `scripts/caption-lab-check.ts`

O laboratório roda **100% no navegador**, sem FFmpeg, sem Flask e sem aaPanel.
Ele reimplementa fielmente a lógica de `backend/app/services/captions.py` para
que a legenda seja **previsível antes de queimar o vídeo**.

Rodar os testes:

```bash
bun scripts/caption-lab-check.ts   # 43 asserções
```

---

## 1. O pipeline correto (aprendido e provado no lab)

```text
ENTRADA                    NORMALIZAÇÃO                MONTAGEM              RENDER
─────────────────────────────────────────────────────────────────────────────────────
SRT colado        ─┐
Transcrição Groq  ─┼─▶ palavras (start,end,text) ─▶ group_words(...) ─▶ build_ass ─▶ FFmpeg -vf ass
Texto corrido     ─┘        (spread_words)            (linhas curtas)     (.ass)      (burn_ass)
```

**Descoberta nº1 (armadilha real):** as linhas devolvidas por `parse_srt`
**não podem ir direto para o ASS**. Elas trazem a frase inteira do bloco SRT
(> 42 caracteres) e ignoram o `words_per_line` do preset. O caminho correto —
que o `legendar.py` já faz na linha 141 — é achatar as palavras e chamar
`group_words` de novo. O lab expõe isso como uma função única:
`linesFromSrt(texto, maxWords)`. O teste 8 falhava justamente quando esse passo
era pulado (21 falhas de "Linha ≤ 42 caracteres") e passou 100% depois.

---

## 2. Regras de tempo (as que fazem a legenda "colar" na fala)

| Regra | Valor | Onde |
| --- | --- | --- |
| Tempo por palavra sem timestamp | proporcional ao nº de caracteres | `spread_words` |
| Duração mínima de uma linha | 0,2 s | `spread_words` |
| Quebra por pausa | gap > **0,65 s** | `group_words` |
| Quebra por tamanho | **42 caracteres** ou `words_per_line` | `group_words` |
| Quebra por pontuação | palavra termina em `.` `!` `?` `…` | `group_words` |
| Correção de sobreposição | palavra anterior recua até `start` da próxima (mín. 0,08 s) | `lines_from_segments` |
| Duração mínima de evento | 0,08 s (0,06 s no typewriter) | `_render_line` |

---

## 3. Estilo: o que cada parâmetro controla

- `size` do preset é **fração da altura** — 0,058 × 1920 = 111 px em 9:16 e
  apenas 62 px em 16:9. É por isso que o mesmo preset "encolhe" em vídeo deitado.
- `font_scale` é limitado a **0,35 – 1,8** no backend; no mínimo o Hormozi cai
  para 55 px (ainda legível). O lab valida essa faixa.
- Posição → alignment ASS: `bottom = 2`, `center = 5`, `top = 8`.
- Margem vertical: `0,14 × altura` embaixo, `0,08 × altura` no topo, `10 px` no
  centro. O diagnóstico avisa quando a margem inferior fica abaixo de 10% da
  altura (zona da UI do TikTok/Reels).
- **Cores são BBGGRR, não RRGGBB.** `#FFE500` (amarelo Hormozi) vira `00E5FF` no
  preset. Quem lê o preset como RGB acha que é ciano — é o erro mais comum ao
  criar um preset novo. Use `hex_rgb_to_ass` / `hexRgbToAss` sempre.

---

## 4. Animações e o ASS que elas geram

| Animação | Estrutura | Tag principal |
| --- | --- | --- |
| `none` | 1 evento por linha | — |
| `fade` | 1 evento por linha | `\fad(120,120)` |
| `karaoke` | 1 evento por linha, sílaba a sílaba | `\kf<centésimos>` |
| `typewriter` | 1 evento por palavra, resto invisível | `\alpha&HFF&` |
| `pop` | 1 evento por palavra | `\fscx118\fscy118\t(...)` |
| `bounce` | 1 evento por palavra | duplo `\t` de escala |
| `shake` | 1 evento por palavra | `\frz` alternando |
| `highlight` | 1 evento por palavra | só troca de cor |
| `boxed` | 1 evento por palavra | `\3c` + `\bord14` |

**Descoberta nº2:** toda palavra ativa precisa terminar com `{\r}`. Sem esse
reset, a cor/escala vaza para as palavras seguintes da mesma linha. Teste
"pop reseta o estilo após a palavra ativa" trava essa regra.

**Descoberta nº3:** o texto é escapado trocando `{` e `}` por parênteses. Se a
transcrição vier com chaves, elas seriam interpretadas como tag ASS e quebrariam
o render. O teste de balanceamento de chaves cobre isso em todos os presets.

---

## 5. O que o laboratório entrega na tela

1. **Entrada dupla** — SRT com timestamps ou texto corrido com duração simulada.
2. **Controles idênticos ao backend** — preset, animação, formato (9:16/16:9/1:1),
   posição, `font_scale` (0,35–1,8) e palavras por linha (1–10).
3. **Preview animado** com player próprio (play/pause e scrub), mostrando a
   palavra ativa na cor real do preset, tamanho proporcional e margem real.
4. **ASS gerado** completo, copiável — o mesmo arquivo que o FFmpeg receberia.
5. **Diagnóstico automático**: sobreposição, 42 caracteres, evento < 80 ms,
   faixa segura de fonte, margem fora da UI e contagem de eventos.
6. **Linhas montadas** com timing, para conferir a quebra frase a frase.

A rota é liberada do login (`PUBLIC_PATHS` em `src/routes/__root.tsx`) porque
não toca em nenhuma API — é ferramenta de bancada.

---

## 6. Cobertura de testes (`bun scripts/caption-lab-check.ts`)

- parsing de timestamp SRT (`,` e `.`, hora cheia);
- SRT → linhas e prova de que a linha crua estoura 42 caracteres;
- distribuição proporcional de tempo e fechamento exato no fim do bloco;
- quebra por `maxWords`, por caracteres, por pausa e por pontuação;
- correção de sobreposição;
- conversão de cor RGB↔BBGGRR e rejeição de hex inválido;
- timestamp ASS (`1:02:03.05`);
- **7 presets × 3 formatos**: cabeçalho, `PlayResY`, eventos, chaves balanceadas
  e diagnóstico limpo;
- limites de `font_scale`, alinhamentos, texto corrido e as tags de karaokê,
  typewriter e pop.

Resultado atual: **43/43 PASS**.

---

## 7. Como usar antes de mexer em produção

1. Cole no lab o SRT real (ou a transcrição da Groq) do vídeo problemático.
2. Reproduza a configuração usada em `/legendar` (preset, posição, escala).
3. Se o diagnóstico acusar algo, o erro está na **lógica**, não no FFmpeg.
4. Só depois de o lab ficar verde, rode o job no aaPanel:
   `bash deploy/safe-update.sh` e teste em `https://viral.vr766.com/legendar`.
5. Ao criar um preset novo: escreva as cores em **BBGGRR**, defina `size` como
   fração da altura e rode os testes — eles varrem todos os presets
   automaticamente.

## 11. Beat sync e animações virais (atualização)

### Detecção de ritmo (`backend/app/services/beatsync.py`)
1. FFmpeg extrai o áudio em PCM mono 22.05 kHz.
2. Calcula-se a energia por janela (onset strength) e a autocorrelação da curva
   para achar o período dominante entre 60 e 190 BPM.
3. `snap_lines()` puxa o início de cada palavra para a batida mais próxima dentro
   de uma tolerância de 0,22 s — fora disso a palavra fica onde estava (evita
   destruir a sincronia da fala).
4. Invariantes garantidas: texto preservado, ordem crescente, duração mínima de
   0,08 s por palavra e nenhum evento sobreposto.

No laboratório o BPM é informado à mão (não há áudio), o resto da matemática é
idêntica — `beatsFromBpm()` + `snapLinesToBeats()` em `src/lib/caption-lab.ts`.

### Animações disponíveis (19)
`auto, pop, karaoke, typewriter, bounce, shake, boxed, none` (originais) mais
`beat, zoom, slide, blur, wave, glitch, neon, rainbow, stamp, flip`.

Regras aprendidas ao renderizar no libass:
- toda palavra ativa precisa terminar com `{\r}`, senão o estilo vaza para o resto da linha;
- `wave` e `rainbow` dependem do índice da palavra (onda alternada / ciclo de 6 cores);
- `neon` usa `\blur` animado — custa mais CPU, mas roda em tempo real no aaPanel;
- chaves `{}` desbalanceadas fazem o libass imprimir a tag como texto: há teste para isso.

### Correção crítica
`WrapStyle: 2` impedia quebra automática e cortava frases longas nas bordas em
9:16. Trocado para `WrapStyle: 0` (quebra inteligente) no backend e no lab.

### Testes
`bun scripts/caption-lab-check.ts` — cobre timings, presets, ASS, as 19 animações,
a grade de batidas e o encaixe no ritmo.
