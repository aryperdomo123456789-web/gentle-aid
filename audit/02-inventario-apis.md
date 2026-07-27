# Inventario de APIs

## Nota metodologica

Nesta copia local do repo eu nao encontrei valores inteiros de chaves expostos em texto puro no historico acessivel. O que existe no codigo e:

- catalogo de provedores
- nomes de variaveis
- prefixos esperados
- aliases legados
- heuristicas de importacao
- mensagens de remediacao que indicam chave invalida, revogada ou expirada

Por isso, o inventario abaixo registra o que o repo realmente contem hoje, sem inventar valores.

## Catalogo principal

| Provedor | Variavel principal | Prefixo esperado | Onde aparece | Leitura de status |
|---|---|---|---|---|
| DeepSeek | `DEEPSEEK_API_KEY` | `sk-` | `backend/app/services/api_keys.py:29-38` | Sem valor encontrado no repo local; formato esperado definido no catalogo. |
| Google Gemini | `GEMINI_API_KEY` | `AIza` | `backend/app/services/api_keys.py:40-62` | O codigo rejeita `AQ.` e `ya29.` e orienta usar chave AI Studio `AIza`; indicio forte de erro de formato quando a entrada vem de OAuth. |
| Groq | `GROQ_API_KEY` | `gsk_` | `backend/app/services/api_keys.py:65-73` | Sem valor encontrado no repo local; prefixo valido definido. |
| OpenRouter | `OPENROUTER_API_KEY` | `sk-or-` | `backend/app/services/api_keys.py:75-83` | Sem valor encontrado no repo local; prefixo valido definido. |
| Mistral | `MISTRAL_API_KEY` | nao definido | `backend/app/services/api_keys.py:85-92` | Sem valor encontrado no repo local. |
| SiliconFlow | `SILICONFLOW_API_KEY` | `sk-` | `backend/app/services/api_keys.py:94-102` | Sem valor encontrado no repo local; prefixo generico. |
| Hugging Face | `HUGGINGFACE_API_KEY` | `hf_` | `backend/app/services/api_keys.py:104-116` | Remediation diz que o token anterior foi revogado e que o correto e um token `Read`. |
| Cohere | `COHERE_API_KEY` | nao definido | `backend/app/services/api_keys.py:118-152` | O texto sugere que trial serve, mas falhas de `valid=false` indicam chave revogada ou de outra conta. |
| Tavily | `TAVILY_API_KEY` | `tvly-` | `backend/app/services/api_keys.py:156-165` | Sem valor encontrado no repo local. |
| Exa | `EXA_API_KEY` | nao definido | `backend/app/services/api_keys.py:167-175` | Sem valor encontrado no repo local. |
| Firecrawl | `FIRECRAWL_API_KEY` | `fc-` | `backend/app/services/api_keys.py:177-185` | Sem valor encontrado no repo local. |
| Jina Reader | `JINA_API_KEY` | `jina_` | `backend/app/services/api_keys.py:187-195` | Sem valor encontrado no repo local. |
| Langfuse | `LANGFUSE_SECRET_KEY` | `sk-lf-` | `backend/app/services/api_keys.py:197-214` | Requer tambem `LANGFUSE_PUBLIC_KEY` (`pk-lf-...`); se faltar a public key o teste fica incompleto. |
| Cloudflare Workers | `CLOUDFLARE_API_TOKEN` | `cfut_` preferencial | `backend/app/services/api_keys.py:216-241` | O codigo aceita token moderno e tambem trata Global API Key legada com `CLOUDFLARE_EMAIL`; hash hex de 32-40 chars e tratado como legado. |
| Whisper API | `WHISPER_API_KEY` | nao definido | `backend/app/services/api_keys.py:243-265` | Pode apontar para `whisper-api.com` ou endpoint OpenAI compatível via `WHISPER_API_BASE`. |
| TikAPI | `TIKAPI_KEY` | nao definido | `backend/app/services/api_keys.py:267-290` | Remediation diz que `403` quase sempre e plano expirado ou chave revogada. |
| Lamatok | `LAMATOK_API_KEY` | nao definido | `backend/app/services/api_keys.py:292-311` | `402` e tratado como saldo zerado, nao necessariamente chave invalida. |

## Alias legados aceitos pelo autofill

Esses nomes entram como sinonimos no import automatico:

| Provedor | Alias | Onde aparece |
|---|---|---|
| DeepSeek | `DEEPSEEK_KEY`, `DEEPSEEK_TOKEN`, `DEEP_SEEK_API_KEY` | `backend/app/services/api_keys.py:654-656` |
| Gemini | `GOOGLE_API_KEY`, `GOOGLE_GEMINI_API_KEY`, `GEMINI_KEY` | `backend/app/services/api_keys.py:654-656` |
| Groq | `GROQ_KEY`, `GROQ_TOKEN` | `backend/app/services/api_keys.py:657-657` |
| OpenRouter | `OPENROUTER_KEY`, `OPEN_ROUTER_API_KEY` | `backend/app/services/api_keys.py:658-658` |
| Mistral | `MISTRAL_KEY` | `backend/app/services/api_keys.py:659-659` |
| SiliconFlow | `SILICON_FLOW_API_KEY`, `SILICONFLOW_KEY` | `backend/app/services/api_keys.py:660-660` |
| Hugging Face | `HF_TOKEN`, `HUGGINGFACEHUB_API_TOKEN`, `HUGGING_FACE_TOKEN` | `backend/app/services/api_keys.py:661-661` |
| Cohere | `COHERE_KEY`, `CO_API_KEY` | `backend/app/services/api_keys.py:662-662` |
| Tavily | `TAVILY_KEY` | `backend/app/services/api_keys.py:663-663` |
| Exa | `EXA_KEY`, `EXA_SEARCH_API_KEY` | `backend/app/services/api_keys.py:664-664` |
| Firecrawl | `FIRECRAWL_KEY` | `backend/app/services/api_keys.py:665-665` |
| Jina | `JINA_TOKEN`, `JINA_READER_KEY` | `backend/app/services/api_keys.py:666-666` |
| Langfuse | `LANGFUSE_SK`, `LANGFUSE_PUBLIC_KEY` | `backend/app/services/api_keys.py:667-667` |
| Cloudflare | `CF_API_TOKEN`, `CLOUDFLARE_TOKEN` | `backend/app/services/api_keys.py:668-668` |
| Whisper | `WHISPER_KEY`, `OPENAI_API_KEY` | `backend/app/services/api_keys.py:669-669` |
| TikAPI | `TIKAPI_API_KEY`, `TIK_API_KEY` | `backend/app/services/api_keys.py:670-670` |
| Lamatok | `LAMATOK_KEY`, `LAMATOK_TOKEN` | `backend/app/services/api_keys.py:671-671` |

## Entradas de documentacao que tambem importam

O arquivo `.env.example` expoe exemplos que nao sao o storage real do cofre:

- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY`
- `EXA_API_KEY`
- `FIRECRAWL_API_KEY`
- `ELEVENLABS_API_KEY`

Referencia: `.env.example:26-34`.

O README reforca que as chaves de provedores devem ir pela Central de APIs e nao ficar versionadas:

- `README.md:116-118`

## O que o repo nao mostrou

Com os comandos locais disponiveis eu nao encontrei:

- valores inteiros de chaves em texto puro
- `.env` versionado
- `TODASAPI.txt` versionado
- `api_keys.json` versionado

O unico arquivo de ambiente que apareceu foi `.env.example`.

## Leitura de validade

Sem acessar os dashboards dos provedores, a melhor leitura possivel e:

- `Gemini`: se a entrada atual for `AQ.` ou `ya29.`, ela esta errada por formato.
- `Hugging Face`: o proprio codigo trata o token anterior como revogado.
- `Cloudflare`: uma chave hex longa provavelmente e Global API Key legada, nao token moderno.
- `TikAPI`: `403` tende a indicar assinatura expirada.
- `Lamatok`: `402` tende a indicar saldo zerado, nao revogacao.

