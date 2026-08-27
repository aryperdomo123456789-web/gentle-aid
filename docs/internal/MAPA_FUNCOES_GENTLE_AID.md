# Mapa de funções — gentle-aid

> Índice gerado estaticamente por AST. Ele descreve o código local auditado e não substitui testes de integração.

**Escopo:** 17 blueprints, 131 funções de blueprint, 28 módulos de serviço e 434 funções de serviço.

## Rotas por blueprint

| Módulo | Método | Endpoint | Função | Linha | Chamadas-chave |
|---|---:|---|---|---:|---|
| `api_v1.py` | `GET` | `/api/v1/health` | `health` | 261 | `bp.get, jsonify` |
| `api_v1.py` | `GET` | `/api/v1/capabilities` | `capabilities` | 267 | `bp.get, require_api_key, jsonify, sorted` |
| `api_v1.py` | `POST` | `/api/v1/transcriptions` | `create_transcription` | 287 | `bp.post, require_api_key, _idempotency_key, isinstance, _parse_common_fields, request.files.get` |
| `api_v1.py` | `GET` | `/api/v1/jobs` | `list_jobs` | 383 | `bp.get, require_api_key, max, request.args.get('status') or ''.strip, request.args.get, jsonify` |
| `api_v1.py` | `GET` | `/api/v1/jobs/<job_id>` | `get_job` | 413 | `bp.get, require_api_key, jobs.get, jsonify, _safe_job_id, problem_response` |
| `api_v1.py` | `POST` | `/api/v1/jobs/<job_id>/cancel` | `cancel_job` | 424 | `bp.post, require_api_key, _idempotency_key, isinstance, jobs.get, idempotency.request_hash` |
| `api_v1.py` | `GET` | `/api/v1/jobs/<job_id>/result` | `get_job_result` | 457 | `bp.get, require_api_key, jobs.get, _api_status, _artifact_path, request.args.get('format') or output.suffix.lstrip('.').lower` |
| `api_v1.py` | `GET` | `/api/v1/usage` | `usage` | 494 | `bp.get, require_api_key, jsonify, jobs.list_jobs, _owns, len` |
| `apis.py` | `GET` | `<dynamic>` | `list_providers` | 24 | `bp.get, _require_owner, api_keys.list_all, jsonify, len, sum` |
| `apis.py` | `GET` | `/api/apis/` | `list_providers` | 24 | `bp.get, _require_owner, api_keys.list_all, jsonify, len, sum` |
| `apis.py` | `PUT` | `/api/apis/<provider_id>` | `update_provider` | 37 | `bp.put, _require_owner, str(payload.get('key', '')).strip, str(payload.get('note', '')).strip, provider.get, jsonify` |
| `apis.py` | `DELETE` | `/api/apis/<provider_id>` | `delete_provider` | 61 | `bp.delete, _require_owner, jsonify, api_keys.delete_key` |
| `apis.py` | `POST` | `/api/apis/<provider_id>/test` | `test_provider` | 71 | `bp.post, _require_owner, api_keys.test_provider, jsonify, api_keys.describe` |
| `apis.py` | `POST` | `/api/apis/import` | `import_keys` | 82 | `bp.post, _require_owner, api_keys.autofill, jsonify, request.get_json, bool` |
| `apis.py` | `POST` | `/api/apis/test-all` | `test_all` | 96 | `bp.post, _require_owner, jsonify, provider.get, api_keys.test_provider, api_keys.list_all` |
| `apis.py` | `GET` | `/api/apis/scan` | `scan` | 108 | `bp.get, _require_owner, jsonify, api_keys.scan_report` |
| `auth.py` | `GET` | `/api/auth/me` | `me` | 37 | `bp.get, current_session, jsonify` |
| `auth.py` | `POST` | `/api/auth/login` | `do_login` | 46 | `bp.post, str(payload.get('email', '')).strip, str, jsonify, issue_session_cookie, request.get_json` |
| `auth.py` | `POST` | `/api/auth/logout` | `do_logout` | 64 | `bp.post, logout, jsonify, clear_session_cookie` |
| `auth.py` | `GET` | `/api/auth/users` | `users` | 72 | `bp.get, _require_actor, jsonify, _json_error, actor.get, list_users` |
| `auth.py` | `POST` | `/api/auth/users` | `create` | 82 | `bp.post, _require_actor, _json_error, request.get_json, create_user, jsonify` |
| `auth.py` | `PUT` | `/api/auth/users/<user_id>` | `edit` | 103 | `bp.put, _require_actor, jsonify, _json_error, request.get_json, update_user` |
| `auth.py` | `DELETE` | `/api/auth/users/<user_id>` | `remove` | 125 | `bp.delete, _require_actor, jsonify, _json_error, delete_user, str` |
| `canva_cleaner.py` | `POST` | `/api/canva-cleaner/run` | `run_job` | 18 | `bp.post, request.form.get, normalize_level, normalize_format, normalize_fit, request.form.get('url') or ''.strip` |
| `discover.py` | `POST` | `/api/discover/search` | `search` | 18 | `bp.post, str(payload.get('query') or payload.get('keyword') or '').strip, str(payload.get('platform') or 'auto').strip().lower, str(payload.get('region') or 'BR').strip, jsonify, request.get_json` |
| `discover.py` | `POST` | `/api/discover/inspect` | `inspect` | 39 | `bp.post, str(payload.get('url') or '').strip, jsonify, request.get_json, payload.get, len` |
| `jobs.py` | `GET` | `<dynamic>` | `list_all` | 38 | `bp.get, _require_session, request.args.get('tool') or ''.strip, request.args.get('status') or ''.strip, (request.args.get('q') or '').strip().lower, _clamp_limit` |
| `jobs.py` | `GET` | `/api/jobs/` | `list_all` | 38 | `bp.get, _require_session, request.args.get('tool') or ''.strip, request.args.get('status') or ''.strip, (request.args.get('q') or '').strip().lower, _clamp_limit` |
| `jobs.py` | `GET` | `/api/jobs/stats` | `stats_only` | 73 | `bp.get, _require_session, jobs.list_jobs, jsonify, jobs.summarize` |
| `jobs.py` | `GET` | `/api/jobs/audit` | `audit_ledger` | 82 | `bp.get, _require_session, _clamp_limit, jsonify, request.args.get, request.args.get('job_id') or ''.strip` |
| `jobs.py` | `GET` | `/api/jobs/<job_id>` | `detail` | 93 | `bp.get, _require_session, jobs.get, jsonify` |
| `jobs.py` | `GET` | `/api/jobs/<job_id>/trace` | `trace` | 104 | `bp.get, _require_session, jobs.get, jobs.read_audit, jsonify, job or {}.get` |
| `jobs.py` | `DELETE` | `/api/jobs/<job_id>` | `remove` | 125 | `bp.delete, _require_session, jobs.delete, jsonify, jobs.get` |
| `jobs.py` | `POST` | `/api/jobs/<job_id>/cancel` | `cancel` | 136 | `bp.post, _require_session, jobs.request_cancel, jsonify, jobs.get` |
| `legendar.py` | `GET` | `/api/legendar/presets` | `list_presets` | 32 | `bp.get, jsonify, captions.preset_catalog, list, transcribe.available` |
| `legendar.py` | `POST` | `/api/legendar/run` | `run_job` | 50 | `bp.post, captions.resolve_preset, request.form.get, (request.form.get('animation') or 'auto').strip().lower, normalize_level, request.form.get('url') or ''.strip` |
| `live.py` | `GET` | `/api/live/options` | `options` | 66 | `bp.get, PLATFORMS.items, jsonify, platforms.append, bool, _stored_key` |
| `live.py` | `GET` | `/api/live/library` | `library` | 88 | `bp.get, config.storage_dir.resolve, sorted, jsonify, config.tool_dir, _media_dir().glob` |
| `live.py` | `GET` | `/api/live/status` | `status` | 125 | `bp.get, jsonify, _platform_from, streamer.status, request.args.get, str` |
| `live.py` | `GET` | `/api/live/sessions` | `sessions` | 134 | `bp.get, jsonify, streamer.sessions` |
| `live.py` | `POST` | `/api/live/start` | `start` | 139 | `bp.post, request.files.getlist, _platform_from, form.get, json.loads, paths.extend` |
| `live.py` | `POST` | `/api/live/stop` | `stop` | 205 | `bp.post, request.get_json, _platform_from, jsonify, streamer.stop, payload.get` |
| `radar.py` | `GET` | `/api/radar/global` | `global_radar` | 20 | `bp.get, _params, request.args.get, jsonify, trends_service.radar, str` |
| `radar.py` | `GET` | `/api/radar/snapshot` | `snapshot` | 33 | `bp.get, jsonify, _params, trends_service.load_radar_snapshot, str` |
| `radar.py` | `GET` | `/api/radar/forecast` | `forecast` | 46 | `bp.get, _params, jsonify, trends_service.forecast, str` |
| `radar.py` | `GET` | `/api/radar/searches` | `searches` | 58 | `bp.get, jsonify, request.args.get('region') or 'BR'.upper, trends_service.google_trends, request.args.get` |
| `recap.py` | `GET` | `/api/recap/catalog` | `catalog` | 34 | `bp.get, jsonify, recap.catalog` |
| `recap.py` | `GET` | `/api/recap/blocks` | `blocks_list` | 39 | `bp.get, jsonify, recap.list_blocks` |
| `recap.py` | `POST` | `/api/recap/blocks` | `blocks_save` | 44 | `bp.post, jsonify, request.get_json, recap.save_block_preset, recap.list_blocks, str` |
| `recap.py` | `DELETE` | `/api/recap/blocks/<preset_id>` | `blocks_delete` | 54 | `bp.delete, jsonify, recap.delete_block_preset, recap.list_blocks` |
| `recap.py` | `POST` | `/api/recap/run` | `run_job` | 61 | `bp.post, form.get('format') or 'short'.strip, FORMATS.get, max, form.get('engine') or 'forge'.strip, form.get('persona_id') or ''.strip` |
| `release_keys.py` | `GET` | `<dynamic>` | `list_release_keys` | 23 | `bp.get, _require_owner, jsonify, release_keys.list_keys` |
| `release_keys.py` | `POST` | `<dynamic>` | `create_release_key` | 31 | `bp.post, _require_owner, str(payload.get('label', '')).strip, payload.get, request.get_json, int` |
| `release_keys.py` | `DELETE` | `/api/access-keys/<key_id>` | `revoke_release_key` | 60 | `bp.delete, _require_owner, jsonify, release_keys.revoke_key, str` |
| `release_keys.py` | `POST` | `/api/access-keys/validate` | `validate_release_key` | 75 | `bp.post, str(payload.get('key') or request.headers.get('X-Api-Key') or request.headers.get('Authorization', '').removeprefix('Bearer ') or '').strip, release_keys.validate_key, jsonify, request.get_json, str` |
| `studio.py` | `GET` | `/api/studio/options` | `options` | 27 | `bp.get, jsonify, storyboard.styles, list, captions.preset_catalog, edge_tts.list_voices` |
| `studio.py` | `POST` | `/api/studio/storyboard` | `make_storyboard` | 48 | `bp.post, str(payload.get('prompt') or '').strip, storyboard.plan, jsonify, request.get_json, len` |
| `studio.py` | `POST` | `/api/studio/run` | `run_job` | 114 | `bp.post, (request.form.get('mode') or 'ia').strip().lower, request.form.get('aspect') or '9:16'.strip, request.form.get('look') or 'cartoon'.strip, request.form.get('voice') or 'pt-BR-AntonioNeural'.strip, request.form.get('persona_id') or ''.strip` |
| `tiktok.py` | `GET` | `/api/tiktok/trends` | `trends` | 23 | `bp.get, jsonify, clean_text, request.args.get('region') or 'BR'.upper, trends_service.tiktok_niche, request.args.get` |
| `tiktok.py` | `POST` | `/api/tiktok/clone` | `clone` | 42 | `bp.post, str(payload.get('url', '')).strip, payload.get, normalize_level, normalize_format, normalize_fit` |
| `transcribe_video.py` | `POST` | `/api/transcribe/run` | `run_job` | 171 | `bp.post, jobs.create_job, jobs.submit, clean_text, ingest.is_supported_url, transcribe.available` |
| `voice.py` | `GET` | `/api/voice/catalog` | `catalog` | 107 | `bp.get, jsonify, voice_engine.available, edge_tts.available, list, voice_engine.list_voices` |
| `voice.py` | `POST` | `/api/voice/preview` | `preview` | 143 | `bp.post, str(payload.get('engine') or 'forge').lower, output_path, request.get_json, request.form.to_dict, isinstance` |
| `voice.py` | `GET` | `/api/voice/script/styles` | `script_styles` | 237 | `bp.get, jsonify, script_doctor.list_styles, script_doctor.llm_available` |
| `voice.py` | `POST` | `/api/voice/script/analyze` | `script_analyze` | 248 | `bp.post, jsonify, request.get_json, request.form.to_dict, isinstance, dict` |
| `voice.py` | `POST` | `/api/voice/script/fix` | `script_fix` | 260 | `bp.post, str, payload.get, time.time, script_doctor.rewrite, round` |
| `voice.py` | `GET` | `/api/voice/voices` | `voices` | 298 | `bp.get, jsonify, voice_engine.available, voice_engine.list_voices` |
| `voice.py` | `GET` | `/api/voice/personas` | `personas_list` | 306 | `bp.get, jsonify, edge_tts.available, voice_forge.list_personas, edge_tts.list_voices` |
| `voice.py` | `POST` | `/api/voice/personas/reset` | `personas_reset` | 316 | `bp.post, voice_forge.reset_factory_presets, jsonify, edge_tts.available, voice_forge.list_personas, edge_tts.list_voices` |
| `voice.py` | `POST` | `/api/voice/personas` | `personas_save` | 328 | `bp.post, request.get_json, request.form.to_dict, voice_forge.save, jsonify, isinstance` |
| `voice.py` | `DELETE` | `/api/voice/personas/<persona_id>` | `personas_delete` | 340 | `bp.delete, jsonify, voice_forge.delete` |
| `voice.py` | `POST` | `/api/voice/personas/clone` | `personas_clone` | 347 | `bp.post, str(request.form.get('name') or upload.filename).strip, request.form.get, jobs.create_job, request.files.get, voice_engine.available` |
| `voice.py` | `POST` | `/api/voice/personas/variants` | `personas_variants` | 400 | `bp.post, dict, base_payload.setdefault, payload.get, jsonify, request.get_json` |
| `voice.py` | `POST` | `/api/voice/personas/bulk` | `personas_bulk` | 433 | `bp.post, payload.get, request.get_json, voice_forge.save_many, jsonify, isinstance` |
| `voice.py` | `POST` | `/api/voice/personas/preview` | `personas_preview` | 449 | `bp.post, dict, payload.setdefault, output_path, jsonify, edge_tts.available` |
| `voice.py` | `POST` | `/api/voice/convert` | `convert` | 517 | `bp.post, request.form.get('engine') or ('elevenlabs' if voice_engine.available() else 'local').lower, request.form.get, request.form.get('voice_id') or ''.strip, request.form.get('persona_id') or ''.strip, jobs.create_job` |
| `voice.py` | `POST` | `/api/voice/tts` | `tts` | 600 | `bp.post, request.form.get('engine') or ('elevenlabs' if voice_engine.available() else 'forge').lower, request.form.get('voice_id') or ''.strip, request.form.get('persona_id') or ''.strip, jobs.create_job, _settings_from_form` |
| `voice.py` | `POST` | `/api/voice/dub` | `dub` | 857 | `bp.post, request.form.get('engine') or 'forge'.lower, request.form.get('persona_id') or ''.strip, request.form.get('voice_id') or ''.strip, (request.form.get('target_lang') or 'auto').strip().lower, jobs.create_job` |
| `youtube.py` | `POST` | `/api/youtube/bypass` | `bypass` | 25 | `bp.post, payload.get, normalize_level, normalize_format, normalize_fit, jobs.create_job` |

## Funções internas dos blueprints

| Módulo | Função | Linha | Docstring/responsabilidade |
|---|---|---:|---|
| `api_v1.py` | `_safe_job_id` | 31 | helper interno sem docstring |
| `api_v1.py` | `_key_owner` | 35 | helper interno sem docstring |
| `api_v1.py` | `_owner_of` | 39 | helper interno sem docstring |
| `api_v1.py` | `_owns` | 47 | helper interno sem docstring |
| `api_v1.py` | `_api_status` | 51 | helper interno sem docstring |
| `api_v1.py` | `_artifact_path` | 67 | Retorna somente um output dentro do storage; rejeita path traversal. |
| `api_v1.py` | `_public_job` | 88 | helper interno sem docstring |
| `api_v1.py` | `_parse_common_fields` | 121 | helper interno sem docstring |
| `api_v1.py` | `_file_fingerprint` | 134 | helper interno sem docstring |
| `api_v1.py` | `_format_timestamp` | 150 | helper interno sem docstring |
| `api_v1.py` | `_render_segments` | 159 | helper interno sem docstring |
| `api_v1.py` | `_run_transcription` | 183 | helper interno sem docstring |
| `api_v1.py` | `_idempotency_key` | 211 | helper interno sem docstring |
| `api_v1.py` | `_replay_or_reserve` | 222 | helper interno sem docstring |
| `apis.py` | `_require_owner` | 13 | helper interno sem docstring |
| `auth.py` | `_json_error` | 25 | helper interno sem docstring |
| `auth.py` | `_require_actor` | 29 | helper interno sem docstring |
| `canva_cleaner.py` | `_work` | 64 | helper interno sem docstring |
| `jobs.py` | `_require_session` | 19 | helper interno sem docstring |
| `jobs.py` | `_clamp_limit` | 28 | helper interno sem docstring |
| `jobs.py` | `matches` | 57 | helper interno sem docstring |
| `legendar.py` | `_float` | 41 | helper interno sem docstring |
| `legendar.py` | `_work` | 133 | helper interno sem docstring |
| `legendar.py` | `_stamp` | 241 | helper interno sem docstring |
| `legendar.py` | `_lines_to_srt` | 249 | helper interno sem docstring |
| `live.py` | `_media_dir` | 25 | helper interno sem docstring |
| `live.py` | `_platform_from` | 31 | helper interno sem docstring |
| `live.py` | `_stored_key` | 38 | helper interno sem docstring |
| `live.py` | `_resolve_library` | 46 | Aceita apenas caminhos relativos dentro do storage — sem path traversal. |
| `radar.py` | `_params` | 13 | helper interno sem docstring |
| `recap.py` | `_work` | 178 | helper interno sem docstring |
| `release_keys.py` | `_require_owner` | 13 | helper interno sem docstring |
| `studio.py` | `_scenes_from_request` | 67 | helper interno sem docstring |
| `studio.py` | `_save_media` | 94 | helper interno sem docstring |
| `tiktok.py` | `_enrich_source_card` | 80 | Quando o clone vem sem card (radar, link colado), busca os dados reais. |
| `tiktok.py` | `_work` | 96 | helper interno sem docstring |
| `transcribe_video.py` | `_segments_to_text` | 21 | helper interno sem docstring |
| `transcribe_video.py` | `_is_youtube_url` | 30 | helper interno sem docstring |
| `transcribe_video.py` | `_download_youtube_source` | 34 | helper interno sem docstring |
| `transcribe_video.py` | `_segments_from_caption_text` | 86 | helper interno sem docstring |
| `transcribe_video.py` | `_fetch_caption_segments` | 102 | helper interno sem docstring |
| `transcribe_video.py` | `_transcribe_youtube` | 143 | helper interno sem docstring |
| `transcribe_video.py` | `_work` | 187 | helper interno sem docstring |
| `voice.py` | `_settings_from_form` | 91 | helper interno sem docstring |
| `voice.py` | `num` | 92 | helper interno sem docstring |
| `voice.py` | `run_clone` | 384 | helper interno sem docstring |
| `voice.py` | `_common_params` | 491 | helper interno sem docstring |
| `voice.py` | `_format_params` | 505 | Formato final do vídeo escolhido pelo operador (só afeta saída com imagem). |
| `voice.py` | `build_timbre_chain` | 661 | Cadeia FFmpeg que troca o timbre e devolve (ou não) a duração original. |
| `voice.py` | `_sweep` | 681 | Apaga arquivos intermediários mesmo quando o job falha no meio. |
| `voice.py` | `_work_convert` | 696 | helper interno sem docstring |
| `voice.py` | `_work_tts` | 800 | helper interno sem docstring |
| `voice.py` | `_work_dub` | 944 | helper interno sem docstring |
| `youtube.py` | `_work` | 72 | helper interno sem docstring |

## Serviços

| Serviço | Função | Linha | Docstring/responsabilidade | Chamadas-chave |
|---|---|---:|---|---|
| `api_auth.py` | `request_id` | 26 | Retorna um identificador de correlação por request sem confiar no cliente. | `getattr, str, uuid4` |
| `api_auth.py` | `_problem_type` | 36 | função de serviço sem docstring | `code.lower().replace, code.lower` |
| `api_auth.py` | `problem_response` | 41 | Cria uma resposta RFC 9457-like sem detalhes internos ou segredos. | `jsonify, _problem_type, code.replace('_', ' ').title, request_id, str` |
| `api_auth.py` | `extract_raw_key` | 72 | Extrai a chave de headers aceitos, nunca de query string ou body. | `request.headers.get('X-API-Key', '').strip, request.headers.get('Authorization', '').strip, authorization.partition, value.strip, request.headers.get` |
| `api_auth.py` | `_scopes` | 85 | função de serviço sem docstring | `info.get, str(value).strip, str` |
| `api_auth.py` | `_scope_allowed` | 90 | função de serviço sem docstring | `_scopes, required_scope.partition` |
| `api_auth.py` | `require_api_key` | 101 | Protege uma rota do data plane com autenticação e escopos. | `wraps, extract_raw_key, release_keys.validate_key, view, problem_response` |
| `api_auth.py` | `decorator` | 108 | função de serviço sem docstring | `wraps, extract_raw_key, release_keys.validate_key, view, problem_response` |
| `api_auth.py` | `wrapped` | 110 | função de serviço sem docstring | `wraps, extract_raw_key, release_keys.validate_key, view, problem_response` |
| `api_auth.py` | `current_api_key` | 149 | Retorna metadados da chave depois que ``require_api_key`` passou. | `getattr, RuntimeError, isinstance, info.get` |
| `api_keys.py` | `_store_file` | 408 | função de serviço sem docstring | `path.parent.mkdir` |
| `api_keys.py` | `_load` | 414 | função de serviço sem docstring | `_store_file, file.exists, json.loads, file.read_text` |
| `api_keys.py` | `_save` | 424 | função de serviço sem docstring | `_store_file, file.write_text, json.dumps, os.chmod` |
| `api_keys.py` | `_now` | 433 | função de serviço sem docstring | `datetime.now(timezone.utc).isoformat, datetime.now` |
| `api_keys.py` | `mask` | 437 | função de serviço sem docstring | `len` |
| `api_keys.py` | `get_key` | 445 | Fonte única de verdade para o resto do backend. | `PROVIDER_BY_ID.get, _load().get, stored.get, os.environ.get, _load` |
| `api_keys.py` | `last_test_ok` | 456 | True/False conforme o último teste; None quando nunca foi testado. | `stored.get, bool, _load().get, isinstance, _load` |
| `api_keys.py` | `rank_providers` | 466 | Ordena provedores: saudáveis primeiro, não testados depois, falhando por último. | `sorted, get_key, last_test_ok` |
| `api_keys.py` | `set_key` | 476 | função de serviço sem docstring | `describe, _load, data.get, entry.update, entry.pop` |
| `api_keys.py` | `delete_key` | 488 | função de serviço sem docstring | `describe, _load, data.pop, _save, sync_env` |
| `api_keys.py` | `_record_test` | 498 | função de serviço sem docstring | `_load, data.setdefault, _save` |
| `api_keys.py` | `describe` | 506 | função de serviço sem docstring | `os.environ.get, _load().get, stored.get, provider.get, bool` |
| `api_keys.py` | `list_all` | 536 | função de serviço sem docstring | `sorted, describe` |
| `api_keys.py` | `_tiny_wav` | 572 | WAV mono 8 kHz com ~0,3 s de silêncio — só para validar credencial de STT. | `struct.pack, len` |
| `api_keys.py` | `_audio_multipart` | 584 | Monta o multipart/form-data com o áudio mínimo do probe de transcrição. | `fields.items, parts.append, f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="probe.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode, _tiny_wav, f'\r\n--{boundary}--\r\n'.encode` |
| `api_keys.py` | `_run_probe` | 604 | Executa um único endpoint de verificação e devolve status/ok/mensagem. | `spec.get, spec.get('extra_headers_env') or {}.items, urllib.request.Request, ssl.create_default_context, os.environ.get` |
| `api_keys.py` | `_probe_key` | 695 | Testa uma chave candidata sem gravar nada no cofre. | `provider.get, _run_probe, result.get, isinstance, candidate.get` |
| `api_keys.py` | `test_provider` | 711 | função de serviço sem docstring | `provider.get, get_key, time.perf_counter, attempt.get, _record_test` |
| `api_keys.py` | `_autofill_worker` | 834 | função de serviço sem docstring | `autofill` |
| `api_keys.py` | `_scan_roots` | 851 | Diretórios onde as chaves podem estar (app atual, app legado, extras). | `os.environ.get, Path, set, str, seen.add` |
| `api_keys.py` | `_scan_paths` | 887 | Varredura recursiva (profundidade limitada) por arquivos de configuração. | `time.time, _scan_roots, _scan_cache.update, len, os.walk` |
| `api_keys.py` | `_harvest` | 926 | Extrai pares NOME=valor / "nome": "valor" de qualquer formato texto. | `_KV.findall, re.compile, name.upper, out.setdefault, value.lower` |
| `api_keys.py` | `_harvest_signatures` | 945 | Captura chaves pelo formato do valor, mesmo sem nome de variável. | `_PREFIX_OWNER.items, re.search, out.setdefault, re.escape, match.group` |
| `api_keys.py` | `scan_report` | 962 | Diagnóstico: o que a varredura enxerga hoje (sem expor as chaves). | `_collect, next, hits.append, str, len` |
| `api_keys.py` | `_parse_legacy_catalog` | 1021 | Lê o formato do TODASAPI.txt do projeto legado (sem NOME=valor). | `text.splitlines, raw.strip, re.match, line.split()[-1].strip, candidate.upper().startswith` |
| `api_keys.py` | `_collect` | 1062 | função de serviço sem docstring | `os.environ.items, _scan_paths, _ALT_CANDIDATES.clear, _ALT_CANDIDATES.update, alts.setdefault` |
| `api_keys.py` | `remember` | 1067 | função de serviço sem docstring | `alts.setdefault, bucket.append` |
| `api_keys.py` | `sync_env` | 1105 | Espelha o cofre no .env da aplicação (0600), preservando as demais variáveis. | `set, str, _load, entries.get(p['id']) or {}.get, env_path.exists` |
| `api_keys.py` | `autofill` | 1145 | Preenche o cofre com chaves encontradas no ambiente e em arquivos legados. | `_collect, _load, sync_env, len, sum` |
| `api_keys.py` | `autofill_once` | 1234 | Dispara a importação uma vez por processo, sem bloquear o boot. | `threading.Thread(target=_run, name='api-keys-autofill', daemon=True).start, os.environ.get, autofill, threading.Thread` |
| `api_keys.py` | `_run` | 1249 | função de serviço sem docstring | `autofill` |
| `auth.py` | `_bootstrap_users` | 25 | Retorna contas iniciais somente quando o operador as fornece por ambiente. | `os.environ.get('OWNER_EMAIL', '').strip().lower, os.environ.get, os.environ.get('DEMO_EMAIL', '').strip().lower, RuntimeError, len` |
| `auth.py` | `_db_path` | 69 | função de serviço sem docstring | `current_app.config.get, Path, str` |
| `auth.py` | `_conn` | 79 | função de serviço sem docstring | `_db_path, path.parent.mkdir, sqlite3.connect, conn.execute, str` |
| `auth.py` | `_now` | 92 | função de serviço sem docstring | `datetime.now(timezone.utc).isoformat, datetime.now` |
| `auth.py` | `_expires_at` | 96 | função de serviço sem docstring | `datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS).isoformat, datetime.now, timedelta` |
| `auth.py` | `migrate` | 100 | função de serviço sem docstring | `_conn, conn.executescript, _seed` |
| `auth.py` | `_seed` | 132 | função de serviço sem docstring | `conn.execute, int, _now, _bootstrap_users, conn.executemany` |
| `auth.py` | `_public_user` | 163 | função de serviço sem docstring | `bool` |
| `auth.py` | `_row_user_by_id` | 176 | função de serviço sem docstring | `conn.execute('SELECT * FROM auth_users WHERE id = ? LIMIT 1', (user_id,)).fetchone, conn.execute` |
| `auth.py` | `_row_user_by_email` | 180 | função de serviço sem docstring | `conn.execute('SELECT * FROM auth_users WHERE lower(email) = lower(?) LIMIT 1', (email,)).fetchone, conn.execute` |
| `auth.py` | `_row_session` | 187 | função de serviço sem docstring | `conn.execute('\n        SELECT s.token, s.user_id, s.created_at, s.last_seen_at, s.expires_at\n          FROM auth_sessions s\n         WHERE s.token = ?\n         LIMIT 1\n        ', (token,)).fetchone, conn.execute` |
| `auth.py` | `_cookie_secure` | 199 | função de serviço sem docstring | `current_app.config.get, isinstance, str(raw).strip().lower, str(raw).strip, str` |
| `auth.py` | `issue_session_cookie` | 208 | função de serviço sem docstring | `response.set_cookie, _cookie_secure` |
| `auth.py` | `clear_session_cookie` | 220 | função de serviço sem docstring | `response.delete_cookie` |
| `auth.py` | `current_session_token` | 224 | função de serviço sem docstring | `request.cookies.get(COOKIE_NAME, '').strip, request.cookies.get` |
| `auth.py` | `_load_current_session` | 229 | função de serviço sem docstring | `current_session_token, migrate, _conn, _row_session, datetime.fromisoformat` |
| `auth.py` | `current_user` | 263 | função de serviço sem docstring | `_load_current_session` |
| `auth.py` | `current_session` | 268 | função de serviço sem docstring | `_load_current_session` |
| `auth.py` | `login` | 272 | função de serviço sem docstring | `migrate, email.strip().lower, _conn, _row_user_by_email, _now` |
| `auth.py` | `logout` | 299 | função de serviço sem docstring | `current_session_token, migrate, _conn, conn.execute` |
| `auth.py` | `list_users` | 308 | função de serviço sem docstring | `migrate, _conn, conn.execute('SELECT * FROM auth_users ORDER BY role DESC, created_at ASC').fetchall, _public_user, conn.execute` |
| `auth.py` | `update_user` | 315 | função de serviço sem docstring | `migrate, _conn, _row_user_by_id, _now, conn.execute` |
| `auth.py` | `create_user` | 367 | função de serviço sem docstring | `migrate, email.strip().lower, actor.get, PermissionError, len` |
| `auth.py` | `delete_user` | 411 | função de serviço sem docstring | `migrate, _conn, _row_user_by_id, conn.execute, ValueError` |
| `beatsync.py` | `ok` | 48 | função de serviço sem docstring | `len` |
| `beatsync.py` | `_decode_pcm` | 55 | função de serviço sem docstring | `array.array, samples.frombytes, str, subprocess.run, len` |
| `beatsync.py` | `_energy_envelope` | 78 | função de serviço sem docstring | `len, range, env.append` |
| `beatsync.py` | `_onset_strength` | 90 | Fluxo positivo em escala log — realça ataques de bumbo/caixa. | `range, len, out.append, max, math.log` |
| `beatsync.py` | `_pick_peaks` | 100 | função de serviço sem docstring | `range, max, min, len, sum` |
| `beatsync.py` | `_estimate_bpm` | 121 | BPM por histograma de intervalos entre ataques, dobrado para 60–190. | `enumerate, max, len, buckets.items, sum` |
| `beatsync.py` | `_phase_align` | 147 | Escolhe o deslocamento da grade que melhor cobre os ataques reais. | `range, abs, min, max` |
| `beatsync.py` | `beats_from_bpm` | 166 | função de serviço sem docstring | `out.append, round` |
| `beatsync.py` | `detect_beats` | 178 | Analisa a trilha do arquivo e devolve o mapa de batidas. | `_decode_pcm, _energy_envelope, _onset_strength, _pick_peaks, _estimate_bpm` |
| `beatsync.py` | `_nearest` | 204 | função de serviço sem docstring | `len, abs` |
| `beatsync.py` | `snap_words` | 220 | Puxa o início de cada palavra para a batida mais próxima dentro da tolerância. | `list, enumerate, zip, _nearest, max` |
| `beatsync.py` | `snap_lines` | 247 | Aplica o snap mantendo o agrupamento já decidido pelo `group_words`. | `zip, snap_words, out.append, Line, max` |
| `captions.py` | `text` | 59 | função de serviço sem docstring | `' '.join((w.text for w in self.words)).strip, ' '.join` |
| `captions.py` | `resolve_preset` | 362 | função de serviço sem docstring | `(preset_id or '').strip().lower, LEGACY_ALIASES.get, _PRESET_MAP.get, preset_id or ''.strip` |
| `captions.py` | `preset_catalog` | 368 | Catálogo enxuto para o frontend montar a galeria. | `` |
| `captions.py` | `_installed_fonts` | 389 | função de serviço sem docstring | `lru_cache, set, out.splitlines, line.split, subprocess.run` |
| `captions.py` | `pick_font` | 405 | função de serviço sem docstring | `_installed_fonts, list, name.lower` |
| `captions.py` | `_ass_color` | 419 | Aceita 'RRGGBB', '#RRGGBB' ou já 'BBGGRR' de 6 dígitos e devolve &HAABBGGRR. | `(value or '').strip().lstrip, value or ''.strip, len, re.fullmatch, raw.upper` |
| `captions.py` | `hex_rgb_to_ass` | 427 | Converte '#RRGGBB' (frontend) para a ordem BBGGRR usada nos presets. | `(value or '').strip().lstrip, raw[4:6] + raw[2:4] + raw[0:2].upper, value or ''.strip, len, re.fullmatch` |
| `captions.py` | `_parse_ts` | 441 | função de serviço sem docstring | `_TS.search, m.groups, int, ms.ljust` |
| `captions.py` | `parse_srt` | 449 | Converte SRT em linhas (sem timing por palavra — distribuído depois). | `re.split, text.strip, rows[0].isdigit, rows[0].partition, ' '.join(rows[1:]).strip` |
| `captions.py` | `_spread_words` | 469 | Distribui o tempo da linha entre as palavras proporcionalmente ao tamanho. | `max, sum, words.append, text.split, Word` |
| `captions.py` | `group_words` | 486 | Agrupa palavras em linhas curtas, quebrando em pausas naturais. | `flush, bucket.append, lines.append, bucket[-1].text.endswith, Line` |
| `captions.py` | `flush` | 493 | função de serviço sem docstring | `lines.append, Line` |
| `captions.py` | `lines_from_segments` | 511 | Aceita objetos com .start/.end/.text (e opcionalmente .words). | `words.sort, zip, group_words, getattr, words.extend` |
| `captions.py` | `_ts` | 548 | função de serviço sem docstring | `max, int, divmod, round` |
| `captions.py` | `_escape` | 557 | função de serviço sem docstring | `text.replace('\\', '\\\\').replace('{', '(').replace('}', ')').replace, text.replace('\\', '\\\\').replace('{', '(').replace, text.replace('\\', '\\\\').replace, text.replace` |
| `captions.py` | `build_ass` | 561 | função de serviço sem docstring | `resolve_preset, max, pick_font, POSITIONS.get, int` |
| `captions.py` | `_dialogue` | 630 | função de serviço sem docstring | `_ts` |
| `captions.py` | `_maybe_emoji` | 644 | função de serviço sem docstring | `text.lower, any` |
| `captions.py` | `_render_line` | 652 | função de serviço sem docstring | `enumerate, _escape, max, ' '.join, events.append` |
| `captions.py` | `render` | 659 | função de serviço sem docstring | `_escape, text.upper` |
| `captions.py` | `_active_token` | 713 | função de serviço sem docstring | `len` |
| `delivery.py` | `_human_size` | 13 | função de serviço sem docstring | `float, len` |
| `delivery.py` | `_format_bitrate` | 27 | função de serviço sem docstring | `` |
| `delivery.py` | `_format_duration` | 36 | função de serviço sem docstring | `max, divmod, int, round` |
| `delivery.py` | `_format_audit_summary` | 47 | função de serviço sem docstring | `int, _human_size, lines.extend, '\n'.join, round` |
| `delivery.py` | `deliver` | 96 | Marca o job como concluído com o arquivo já esterilizado. | `jobs.check_cancelled, _format_audit_summary, jobs.register_artifact, jobs.log, jobs.update` |
| `discovery.py` | `_run_json` | 32 | função de serviço sem docstring | `media.run, json.loads, raw.index` |
| `discovery.py` | `_duration_label` | 45 | função de serviço sem docstring | `max, int` |
| `discovery.py` | `_date_label` | 50 | função de serviço sem docstring | `str, entry.get, upload.isdigit, datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime, len` |
| `discovery.py` | `_platform_of` | 63 | função de serviço sem docstring | `TIKTOK_URL_RE.search, YOUTUBE_URL_RE.search` |
| `discovery.py` | `_embed_url` | 71 | função de serviço sem docstring | `` |
| `discovery.py` | `_thumbnail` | 81 | função de serviço sem docstring | `entry.get, str, isinstance, last.get` |
| `discovery.py` | `_normalize` | 93 | função de serviço sem docstring | `str(entry.get('id') or '').strip, str(entry.get('webpage_url') or entry.get('url') or '').strip, _platform_of, entry.get('description') or entry.get('title') or 'Sem legenda'.strip, int` |
| `discovery.py` | `_entries` | 148 | função de serviço sem docstring | `payload.get, isinstance` |
| `discovery.py` | `_single_url` | 159 | função de serviço sem docstring | `_run_json, _entries` |
| `discovery.py` | `_flat` | 166 | função de serviço sem docstring | `_run_json, _entries, str` |
| `discovery.py` | `_tiktok_profile` | 181 | função de serviço sem docstring | `_flat, handle.lstrip` |
| `discovery.py` | `_tiktok_keyword` | 185 | função de serviço sem docstring | `_flat, re.sub` |
| `discovery.py` | `_youtube_keyword` | 192 | função de serviço sem docstring | `_flat` |
| `discovery.py` | `search` | 199 | Descoberta unificada: keyword, `@perfil` ou URL direta. | `query or ''.strip, max, set, results.sort, min` |
| `discovery.py` | `_parse_vtt` | 275 | função de serviço sem docstring | `text.splitlines, ' '.join(lines)[:max_chars].strip, _VTT_TAG_RE.sub('', raw_line).strip, line.upper().startswith, line.isdigit` |
| `discovery.py` | `captions` | 293 | Baixa a legenda (oficial ou automática) do vídeo e devolve o texto. | `subs_dir.mkdir, sorted, media.run, subs_dir.glob, _parse_vtt` |
| `discovery.py` | `inspect` | 344 | Card completo de um link direto: métricas, descrição, player e legenda. | `url or ''.strip, _single_url, caption.get, url.startswith, ValueError` |
| `dubbing.py` | `_llm` | 69 | função de serviço sem docstring | `api_keys.rank_providers, list, api_keys.get_key, json.dumps({'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.2, 'response_format': {'type': 'json_object'}}).encode, urllib.request.Request` |
| `dubbing.py` | `normalize_language` | 115 | Qualquer forma de nomear o idioma → código curto (`pt`, `en`, …). | `(value or '').strip().lower().replace, _LANG_ALIASES.items, raw.split, (value or '').strip().lower, value or ''.strip` |
| `dubbing.py` | `same_language` | 126 | função de serviço sem docstring | `normalize_language, bool` |
| `dubbing.py` | `llm_available` | 134 | Há alguma chave de LLM capaz de traduzir o roteiro? | `any, api_keys.get_key` |
| `dubbing.py` | `missing_llm_message` | 140 | função de serviço sem docstring | `LANGUAGES.get` |
| `dubbing.py` | `translate` | 148 | Traduz preservando a quantidade e a ordem dos trechos. | `LANGUAGES.get, range, jobs.log, llm_available, DubbingError` |
| `dubbing.py` | `resolve_voice` | 202 | Escolhe o locutor certo para o idioma alvo. | `edge_tts.voice_for_language, jobs.log, LANGUAGES.get` |
| `dubbing.py` | `_clean` | 221 | função de serviço sem docstring | `re.sub('\\s+', ' ', text).strip, re.sub` |
| `dubbing.py` | `_synth` | 225 | função de serviço sem docstring | `voice_forge.get, voice_engine.text_to_speech, edge_tts.synthesize` |
| `dubbing.py` | `_fit` | 240 | Ajusta o trecho à janela original. Devolve a duração final real. | `media.probe_duration, max, steps.append, ','.join, media.run` |
| `dubbing.py` | `_silence` | 273 | função de serviço sem docstring | `media.run, str, max` |
| `dubbing.py` | `_concat` | 285 | função de serviço sem docstring | `listing.write_text, media.run, listing.unlink, '\n'.join, str` |
| `dubbing.py` | `build_track` | 300 | Monta a trilha dublada inteira, sincronizada com o vídeo original. | `work.mkdir, enumerate, _concat, work.glob, work.rmdir` |
| `dubbing.py` | `apply_persona` | 350 | Aplica a assinatura acústica se for voz DSP (Edge). Neurais já saem prontas. | `voice_forge.filter_chain, media.run, src.unlink, src.replace, str` |
| `dubbing.py` | `mix_with_background` | 372 | Mantém a trilha original em volume baixo (música/ambiência) sob a dublagem. | `media.run, voice_engine.swap_video_audio, str` |
| `edge_tts.py` | `language_of` | 66 | `pt-BR-AntonioNeural` → `pt`. | `(voice_id or '').split('-', 1)[0].lower, voice_id or ''.split` |
| `edge_tts.py` | `is_female` | 71 | função de serviço sem docstring | `voice_id or ''.lower, any` |
| `edge_tts.py` | `voice_for_language` | 76 | Voz nativa do idioma alvo, mantendo o gênero da voz preferida. | `(language or '').split('-', 1)[0].lower, LANG_VOICES.get, language_of, is_female, language or ''.split` |
| `edge_tts.py` | `_module` | 98 | função de serviço sem docstring | `` |
| `edge_tts.py` | `available` | 106 | função de serviço sem docstring | `_module` |
| `edge_tts.py` | `list_voices` | 110 | função de serviço sem docstring | `_module, voices.sort, list, _run_async, ', '.join` |
| `edge_tts.py` | `split_text` | 137 | função de serviço sem docstring | `text.strip, current.strip, len, re.findall, chunks.append` |
| `edge_tts.py` | `_run_async` | 161 | Executa a corrotina em um loop próprio, sem depender do `asyncio.run`. | `asyncio.new_event_loop, asyncio.set_event_loop, loop.run_until_complete, loop.close` |
| `edge_tts.py` | `_synth_one` | 181 | função de serviço sem docstring | `_module, module.Communicate, communicate.save, str` |
| `edge_tts.py` | `synthesize` | 194 | Gera narração bruta (sem persona aplicada) em WAV 48 kHz mono. | `_module, split_text, workdir.mkdir, jobs.log, EdgeTTSError` |
| `idempotency.py` | `_db_path` | 33 | função de serviço sem docstring | `has_app_context, current_app.config.get, Path, str` |
| `idempotency.py` | `_conn` | 42 | função de serviço sem docstring | `_db_path, conn.execute, sqlite3.connect, conn.commit, conn.close` |
| `idempotency.py` | `_now` | 60 | função de serviço sem docstring | `datetime.now` |
| `idempotency.py` | `_iso` | 64 | função de serviço sem docstring | `value.isoformat` |
| `idempotency.py` | `request_hash` | 68 | Hash canônico de método/rota/payload já sanitizados. | `'\n'.join, hashlib.sha256(canonical.encode('utf-8')).hexdigest, str, hashlib.sha256, canonical.encode` |
| `idempotency.py` | `migrate` | 74 | Cria a tabela de idempotência; executar apenas por comando aprovado. | `_conn, conn.executescript` |
| `idempotency.py` | `_cleanup_expired` | 96 | função de serviço sem docstring | `conn.execute` |
| `idempotency.py` | `reserve` | 100 | Reserva a chave ou devolve a decisão anterior. | `str(consumer_id).strip, str(key).strip, _now, _iso, ValueError` |
| `idempotency.py` | `release` | 169 | Libera uma reserva quando o recurso não foi aceito na fila. | `_conn, conn.execute, str(consumer_id).strip, str(key).strip, str` |
| `idempotency.py` | `record` | 178 | Grava a resposta segura que será reproduzida em retries. | `_conn, conn.execute, IdempotencyRecordUnavailable, int, json.dumps` |
| `ingest.py` | `is_supported_url` | 16 | função de serviço sem docstring | `bool, url.startswith, len` |
| `ingest.py` | `download_source` | 20 | Baixa o vídeo da URL para a pasta de uploads e devolve o caminho. | `config.uploads_dir.mkdir, jobs.log, media.run, jobs.update, jobs.register_artifact` |
| `ingest.py` | `resolve_source` | 55 | Devolve o arquivo local, baixando da URL quando não houve upload. | `ValidationError, download_source` |
| `jobs.py` | `_now` | 85 | função de serviço sem docstring | `datetime.now(timezone.utc).isoformat, datetime.now` |
| `jobs.py` | `tool_label` | 89 | função de serviço sem docstring | `TOOL_LABELS.get` |
| `jobs.py` | `_job_file` | 93 | função de serviço sem docstring | `` |
| `jobs.py` | `_cancel_file` | 97 | Sinal de cancelamento em disco — funciona entre workers do Gunicorn. | `` |
| `jobs.py` | `_audit_file` | 102 | função de serviço sem docstring | `` |
| `jobs.py` | `_parse_iso` | 107 | função de serviço sem docstring | `datetime.fromisoformat, parsed.replace, isinstance` |
| `jobs.py` | `_duration_ms` | 119 | função de serviço sem docstring | `_parse_iso, max, job.get, datetime.now, int` |
| `jobs.py` | `_normalize` | 127 | Garante que jobs antigos em disco tenham o mesmo formato dos novos. | `job.setdefault, tool_label, _duration_ms, job.get` |
| `jobs.py` | `_pid_alive` | 149 | função de serviço sem docstring | `os.kill, int` |
| `jobs.py` | `_is_orphan` | 163 | Job não-terminal cujo processo dono não bate mais o coração. | `job.get, datetime.now(timezone.utc) - beat.total_seconds, _pid_alive, _parse_iso, datetime.now` |
| `jobs.py` | `_write_job_file` | 182 | função de serviço sem docstring | `config.jobs_dir.mkdir, _job_file(job['job_id']).write_text, json.dumps, _job_file` |
| `jobs.py` | `_heal` | 192 | Converte job órfão em falha explícita — nunca deixa 'processando' eterno. | `_now, list, events.append, lines.append, _write_job_file` |
| `jobs.py` | `reconcile_orphans` | 217 | Roda no boot: fecha jobs que ficaram presos em `running` após restart. | `list, _normalize, data.get, _now, _write_job_file` |
| `jobs.py` | `audit` | 257 | Grava uma linha imutável na trilha global (sobrevive ao delete do job). | `_now, config.jobs_dir.mkdir, _audit_file().open, handle.write, _audit_file` |
| `jobs.py` | `read_audit` | 275 | função de serviço sem docstring | `_audit_file, reversed, file.exists, file.read_text(encoding='utf-8').splitlines, line.strip` |
| `jobs.py` | `create_job` | 303 | função de serviço sem docstring | `_now, _event, audit, tool_label, threading.Event` |
| `jobs.py` | `_event` | 344 | Registra um evento estruturado + a linha legível equivalente. | `_now, persist, _jobs.get, list, events.append` |
| `jobs.py` | `log` | 366 | Log padrão de ferramenta (compatível com as chamadas existentes). | `_event` |
| `jobs.py` | `stage` | 371 | Marca a entrada em um estágio nomeado — padrão para todas as ferramentas. | `update, _event, max, min, int` |
| `jobs.py` | `update` | 387 | função de serviço sem docstring | `persist, _jobs.get, job.get, job.update, _now` |
| `jobs.py` | `register_artifact` | 407 | função de serviço sem docstring | `persist, _jobs.get, list, _now, _event` |
| `jobs.py` | `cancel_event` | 425 | função de serviço sem docstring | `_cancel_events.get, threading.Event` |
| `jobs.py` | `is_cancelled` | 438 | Vale para o processo atual **e** para cancelamentos vindos de outro worker. | `cancel_event(job_id).is_set, time.monotonic, _cancel_cache.get, _cancel_file(job_id).exists, cancel_event(job_id).set` |
| `jobs.py` | `check_cancelled` | 456 | Ponto de checagem padrão para trabalhos longos. | `is_cancelled, JobCancelled` |
| `jobs.py` | `request_cancel` | 462 | função de serviço sem docstring | `get, cancel_event(job_id).set, audit, _event, update` |
| `jobs.py` | `_done_event` | 489 | função de serviço sem docstring | `_done_events.get, threading.Event` |
| `jobs.py` | `wait` | 498 | função de serviço sem docstring | `event.wait, _done_events.get` |
| `jobs.py` | `get` | 506 | função de serviço sem docstring | `_job_file, file.exists, _jobs.get, _heal, _normalize` |
| `jobs.py` | `list_jobs` | 520 | função de serviço sem docstring | `snapshot.items, sorted, _heal, config.jobs_dir.glob, json.loads` |
| `jobs.py` | `summarize` | 546 | Estatísticas padronizadas usadas pela Central de Jobs. | `by_tool.setdefault, job.get, int, len, sum` |
| `jobs.py` | `persist` | 577 | Grava o job em disco. Com `throttle`, no máximo 1x por segundo. | `time.monotonic, _last_persist.get, config.jobs_dir.mkdir, _job_file(job_id).with_suffix, tmp.write_text` |
| `jobs.py` | `_touch_heartbeat` | 611 | função de serviço sem docstring | `persist, _jobs.get, _now, job.get` |
| `jobs.py` | `_heartbeat_loop` | 622 | Prova de vida periódica: sem ela, o job é declarado interrompido. | `_shutting_down.is_set, _shutting_down.wait, _touch_heartbeat, _jobs.items, job.get` |
| `jobs.py` | `_run_job` | 636 | função de serviço sem docstring | `_done_event, is_cancelled, update, done.set, work` |
| `jobs.py` | `_worker_loop` | 694 | função de serviço sem docstring | `_queue.get, _run_job, _queue.task_done, _shutting_down.is_set` |
| `jobs.py` | `_ensure_pool` | 709 | função de serviço sem docstring | `range, threading.Thread(target=_heartbeat_loop, name='viral-job-heartbeat', daemon=True).start, max, threading.Thread(target=_worker_loop, name=f'viral-job-{index}', daemon=True).start, threading.Thread` |
| `jobs.py` | `shutdown` | 722 | Encerramento limpo: para o batimento e não aceita trabalho novo. | `_shutting_down.set` |
| `jobs.py` | `queue_depth` | 727 | função de serviço sem docstring | `_queue.qsize` |
| `jobs.py` | `submit` | 731 | Executa o trabalho pesado fora do request, capturando qualquer falha. | `_ensure_pool, _done_event(job_id).clear, audit, _touch_heartbeat, _queue.put` |
| `jobs.py` | `fail` | 741 | Marca falha de validação antes do job entrar na fila. | `_event, update, _now` |
| `jobs.py` | `delete` | 747 | Remove o job do registro em memória, o JSON e os arquivos gerados. | `request_cancel, wait, get, audit, _cancel_cache.pop` |
| `media.py` | `run` | 48 | Executa um comando externo com log ao vivo no painel. | `threading.Event, threading.Thread, thread.start, time.monotonic, thread.join` |
| `media.py` | `reader` | 72 | função de serviço sem docstring | `finished.set, iter, raw.rstrip, output.append, jobs.log` |
| `media.py` | `sanitize_video` | 128 | Esteriliza um vídeo (compatibilidade com a assinatura antiga). | `sterilize` |
| `media.py` | `_escape_filter_path` | 150 | função de serviço sem docstring | `str(path).replace('\\', '/').replace(':', '\\:').replace, str(path).replace('\\', '/').replace, str(path).replace, str` |
| `media.py` | `subtitle_filter` | 154 | Monta o filtro `subtitles` já escapado para uso dentro do -vf. | `SUBTITLE_ALIGNMENT.get, SUBTITLE_STYLES.get, _escape_filter_path` |
| `media.py` | `ass_filter` | 161 | Filtro `ass` — mantém todas as tags de animação do estúdio de legendas. | `_escape_filter_path` |
| `media.py` | `burn_subtitles` | 166 | Queima legendas e esteriliza no MESMO encode (uma única passada). | `sterilize, subtitle_filter` |
| `media.py` | `burn_ass` | 186 | Queima um ASS animado e esteriliza na mesma passada. | `sterilize, ass_filter` |
| `recap.py` | `dict` | 94 | função de serviço sem docstring | `round` |
| `recap.py` | `dict` | 111 | função de serviço sem docstring | `round` |
| `recap.py` | `_blocks_file` | 124 | função de serviço sem docstring | `config.config_dir.mkdir` |
| `recap.py` | `_load_blocks` | 129 | função de serviço sem docstring | `_blocks_file, path.exists, json.loads, isinstance, path.read_text` |
| `recap.py` | `_save_blocks` | 140 | função de serviço sem docstring | `_blocks_file().write_text, json.dumps, _blocks_file` |
| `recap.py` | `slugify` | 144 | função de serviço sem docstring | `re.sub('[^a-z0-9]+', '_', (name or '').lower()).strip, re.sub, name or ''.lower, int, time.time` |
| `recap.py` | `list_blocks` | 149 | função de serviço sem docstring | `list, items.sort, _load_blocks().values, _load_blocks, item.get` |
| `recap.py` | `save_block_preset` | 155 | função de serviço sem docstring | `str(payload.get('name') or '').strip, _load_blocks, _save_blocks, RecapError, str(payload.get('id') or '').strip` |
| `recap.py` | `delete_block_preset` | 174 | função de serviço sem docstring | `_load_blocks, data.pop, _save_blocks` |
| `recap.py` | `text_ai_available` | 198 | função de serviço sem docstring | `any, api_keys.get_key` |
| `recap.py` | `vision_available` | 202 | função de serviço sem docstring | `bool, api_keys.get_key` |
| `recap.py` | `_extract_json` | 206 | função de serviço sem docstring | `raw.find, raw.rfind, json.loads, isinstance` |
| `recap.py` | `_llm_json` | 217 | Chama o primeiro LLM disponível e devolve JSON. Levanta se todos falharem. | `api_keys.rank_providers, RecapError, list, api_keys.get_key, _http_json` |
| `recap.py` | `_vision_gemini` | 256 | função de serviço sem docstring | `parts.append, _http_json, _extract_json, jobs.log, _shots_from` |
| `recap.py` | `_vision_openrouter` | 302 | função de serviço sem docstring | `base64.b64encode(path.read_bytes()).decode, content.append, _http_json, _extract_json, jobs.log` |
| `recap.py` | `_shots_from` | 340 | função de serviço sem docstring | `shots.sort, parsed.get, shots.append, int, str(item['d']).strip` |
| `recap.py` | `sample_frames` | 355 | Tira fotos do vídeo em intervalos regulares para o modelo multimodal ver. | `max, workdir.mkdir, range, jobs.log, min` |
| `recap.py` | `describe_shots` | 381 | Descreve as cenas do vídeo. Nunca derruba o job: sem visão, devolve []. | `sample_frames, vision_available, jobs.log, api_keys.get_key, _vision_gemini` |
| `recap.py` | `_timeline_text` | 408 | Linha do tempo unificada (fala + cena) que o LLM lê para escrever o recap. | `rows.sort, re.sub('\\s+', ' ', seg.text).strip, rows.append, len, '\n'.join` |
| `recap.py` | `_mmss` | 428 | função de serviço sem docstring | `max, divmod, int, round` |
| `recap.py` | `build_brief` | 437 | Descobre nicho, tom, personagens e o arco da história. | `jobs.stage, _llm_json, jobs.log, _timeline_text, brief.get` |
| `recap.py` | `_parse_ts` | 465 | Aceita '1:23', '01:23:45' ou segundos e devolve segundos dentro do vídeo. | `isinstance, max, float, str(value or '').strip, text.split` |
| `recap.py` | `_beats_from_payload` | 484 | função de serviço sem docstring | `parsed.get, out.append, script_doctor.clean_for_speech, len, Beat` |
| `recap.py` | `_slice_window` | 497 | função de serviço sem docstring | `key` |
| `recap.py` | `write_beats` | 501 | Escreve o roteiro do recap ancorado em timestamps reais do vídeo. | `jobs.stage, script_doctor.get_style, int, max, range` |
| `recap.py` | `_insert_fixed_blocks` | 592 | Encaixa abertura, meio e fecho do operador sem quebrar a cronologia. | `script_doctor.clean_for_speech, blocks.get('abertura') or ''.strip, blocks.get('meio') or ''.strip, blocks.get('fecho') or ''.strip, out.append` |
| `recap.py` | `_has_audio` | 619 | função de serviço sem docstring | `any, media.probe, isinstance, info.get, s.get` |
| `recap.py` | `_synth` | 628 | função de serviço sem docstring | `voice_engine.text_to_speech, edge_tts.synthesize` |
| `recap.py` | `_apply_persona` | 636 | função de serviço sem docstring | `voice_forge.filter_chain, media.run, src.unlink, str, ','.join` |
| `recap.py` | `_frame_filter` | 650 | função de serviço sem docstring | `` |
| `recap.py` | `_render_beat` | 662 | Recorta o trecho do vídeo exatamente na duração da narração e mixa o áudio. | `max, media.run, min, str, RecapError` |
| `recap.py` | `_concat` | 717 | função de serviço sem docstring | `listing.write_text, media.run, listing.unlink, '\n'.join, str` |
| `recap.py` | `_concat_batched` | 737 | Cola em lotes e depois cola os lotes — escala para centenas de blocos. | `stage_dir.mkdir, len, _concat, range, sweep` |
| `recap.py` | `narrate_and_assemble` | 761 | Narra cada bloco, monta o clipe correspondente e cola tudo em `dst`. | `jobs.stage, workdir.mkdir, _has_audio, enumerate, _concat_batched` |
| `recap.py` | `caption_lines` | 862 | Converte os blocos narrados em linhas de legenda na régua da timeline. | `captions.lines_from_segments, Segment` |
| `recap.py` | `sweep` | 874 | Remove intermediários sem nunca derrubar o job. | `path.is_dir, sorted, path.rmdir, path.unlink, path.rglob` |
| `recap.py` | `catalog` | 893 | função de serviço sem docstring | `list, script_doctor.list_styles, voice_forge.list_personas, captions.preset_catalog, list_blocks` |
| `release_keys.py` | `_db_path` | 36 | função de serviço sem docstring | `current_app.config.get, Path, has_app_context, str` |
| `release_keys.py` | `_conn` | 46 | função de serviço sem docstring | `_db_path, path.parent.mkdir, sqlite3.connect, conn.execute, str` |
| `release_keys.py` | `_now` | 59 | função de serviço sem docstring | `datetime.now(timezone.utc).isoformat, datetime.now` |
| `release_keys.py` | `_dt` | 63 | função de serviço sem docstring | `datetime.fromisoformat` |
| `release_keys.py` | `_hash` | 67 | função de serviço sem docstring | `hashlib.sha256(raw_key.encode('utf-8')).hexdigest, hashlib.sha256, raw_key.encode` |
| `release_keys.py` | `_prefix` | 71 | função de serviço sem docstring | `len` |
| `release_keys.py` | `migrate` | 77 | função de serviço sem docstring | `_conn, conn.executescript` |
| `release_keys.py` | `_public` | 101 | função de serviço sem docstring | `_dt, datetime.now, list, max, json.loads` |
| `release_keys.py` | `list_keys` | 127 | função de serviço sem docstring | `migrate, _conn, conn.execute('SELECT * FROM release_keys ORDER BY created_at DESC, label ASC').fetchall, _public, conn.execute` |
| `release_keys.py` | `_normalize_scopes` | 136 | função de serviço sem docstring | `isinstance, part.strip, str(scope).strip, scopes.split, str` |
| `release_keys.py` | `create_key` | 145 | função de serviço sem docstring | `migrate, _normalize_scopes, sorted, _now, datetime.now(timezone.utc) + timedelta(days=expires_in_days).isoformat` |
| `release_keys.py` | `revoke_key` | 204 | função de serviço sem docstring | `migrate, actor.get, PermissionError, _conn, conn.execute('SELECT * FROM release_keys WHERE id = ? LIMIT 1', (key_id,)).fetchone` |
| `release_keys.py` | `validate_key` | 223 | função de serviço sem docstring | `raw_key.strip, migrate, _hash, _conn, conn.execute('SELECT * FROM release_keys WHERE secret_hash = ? LIMIT 1', (hashed,)).fetchone` |
| `script_doctor.py` | `list_styles` | 294 | função de serviço sem docstring | `style.items` |
| `script_doctor.py` | `get_style` | 301 | função de serviço sem docstring | `` |
| `script_doctor.py` | `_split_sentences` | 311 | função de serviço sem docstring | `re.split, text.strip, p.strip` |
| `script_doctor.py` | `clean_for_speech` | 316 | Arruma o que sempre estraga narração, sem depender de IA. | `text.replace('\r\n', '\n').replace, re.sub, _ABBREV.items, _ORDINALS.items, out.split` |
| `script_doctor.py` | `analyze` | 360 | Diagnóstico numérico do roteiro — o mesmo que o painel do chat mostra. | `_split_sentences, re.findall, text.strip, problems.append, len` |
| `script_doctor.py` | `llm_available` | 415 | função de serviço sem docstring | `any, api_keys.get_key` |
| `script_doctor.py` | `_system_prompt` | 419 | função de serviço sem docstring | `int` |
| `script_doctor.py` | `rewrite` | 441 | Devolve o roteiro corrigido. Usa IA quando há chave; senão, correção local. | `get_style, clean_for_speech, instruction.strip, api_keys.rank_providers, list` |
| `sterilizer.py` | `normalize_format` | 97 | Aceita apelidos ('vertical', 'shorts', '9x16') e devolve a chave canônica. | `str(value or '').strip().lower, unicodedata.normalize, ''.join, re.sub, _FORMAT_ALIASES.get` |
| `sterilizer.py` | `normalize_fit` | 106 | função de serviço sem docstring | `str(value or '').strip().lower, str(value or '').strip, str` |
| `sterilizer.py` | `format_resolution` | 113 | função de serviço sem docstring | `VIDEO_FORMATS.get` |
| `sterilizer.py` | `_orientation_of` | 117 | função de serviço sem docstring | `` |
| `sterilizer.py` | `format_output_size` | 127 | Resolução final do formato escolhido, sem inflar fontes pequenas. | `format_resolution, max, _even, int` |
| `sterilizer.py` | `build_format_filters` | 143 | Reenquadra para o formato escolhido pelo operador. | `format_resolution, format_output_size` |
| `sterilizer.py` | `file_hashes` | 184 | MD5 + SHA-256 do arquivo (fingerprint de entrega, não uso criptográfico). | `hashlib.md5, hashlib.sha256, path.open, md5.hexdigest, sha.hexdigest` |
| `sterilizer.py` | `md5` | 195 | função de serviço sem docstring | `file_hashes` |
| `sterilizer.py` | `normalize_level` | 199 | função de serviço sem docstring | `str(level).strip().lower, unicodedata.normalize, ''.join, re.sub, _LEVEL_ALIASES.get` |
| `sterilizer.py` | `unique` | 259 | função de serviço sem docstring | `bool` |
| `sterilizer.py` | `as_dict` | 262 | função de serviço sem docstring | `` |
| `sterilizer.py` | `probe` | 299 | função de serviço sem docstring | `Probe, data.get, json.loads, float, int` |
| `sterilizer.py` | `probe_duration` | 357 | função de serviço sem docstring | `probe` |
| `sterilizer.py` | `_even` | 364 | função de serviço sem docstring | `max` |
| `sterilizer.py` | `build_video_filters` | 368 | Mutação estrutural — imperceptível ao humano, letal para fingerprint. | `{'leve': 0.35, 'media': 1.0, 'agressiva': 1.7, 'extrema': 2.4}.get, {'portrait': (1.15, 0.9), 'landscape': (0.9, 1.15), 'square': (1.0, 1.0)}.get, filters.append, _even, int` |
| `sterilizer.py` | `build_audio_filters` | 427 | função de serviço sem docstring | `filters.extend, rng.uniform` |
| `sterilizer.py` | `_fake_identity` | 487 | função de serviço sem docstring | `datetime.now, timedelta, rng.choice, created.strftime, str` |
| `sterilizer.py` | `pick_bitrate` | 500 | função de serviço sem docstring | `rng.randint` |
| `sterilizer.py` | `resolve_level` | 506 | Escolhe o melhor preset quando o operador deixa em modo automático. | `max, normalize_level, float` |
| `sterilizer.py` | `build_command` | 527 | função de serviço sem docstring | `_fake_identity, dst.suffix.lower, next, list, pick_bitrate` |
| `sterilizer.py` | `_parse_progress_seconds` | 696 | função de serviço sem docstring | `line.startswith, line.split('=', 1)[1].strip, re.fullmatch, int, max` |
| `sterilizer.py` | `sterilize` | 716 | Esteriliza `src` em `dst` e devolve o relatório da operação. | `normalize_format, normalize_fit, probe, resolve_level, file_hashes` |
| `sterilizer.py` | `on_line` | 770 | função de serviço sem docstring | `line.startswith, _parse_progress_seconds, int, min, jobs_service.update` |
| `storyboard.py` | `look` | 92 | função de serviço sem docstring | `` |
| `storyboard.py` | `styles` | 99 | Reaproveita o catálogo narrativo do Doutor de Roteiro. | `` |
| `storyboard.py` | `llm_available` | 107 | função de serviço sem docstring | `any, api_keys.get_key` |
| `storyboard.py` | `_system_prompt` | 111 | função de serviço sem docstring | `max, round` |
| `storyboard.py` | `_fallback` | 134 | Sem chave de IA: quebra o próprio texto do usuário em cenas. | `clean_for_speech, max, round, p.strip, len` |
| `storyboard.py` | `_normalize_scene` | 157 | função de serviço sem docstring | `clean_for_speech, isinstance, str(raw.get('narracao') or raw.get('narration') or '').strip, float, max` |
| `storyboard.py` | `plan` | 178 | Devolve `{title, hook, cta, scenes[], provider, fallback}`. | `get_style, max, instruction.strip, api_keys.rank_providers, _fallback` |
| `streamer.py` | `_now` | 96 | função de serviço sem docstring | `datetime.now(timezone.utc).isoformat, datetime.now` |
| `streamer.py` | `_live_dir` | 103 | função de serviço sem docstring | `path.mkdir` |
| `streamer.py` | `_state_file` | 109 | função de serviço sem docstring | `_live_dir` |
| `streamer.py` | `_stop_file` | 113 | função de serviço sem docstring | `_live_dir` |
| `streamer.py` | `_playlist_file` | 117 | função de serviço sem docstring | `_live_dir` |
| `streamer.py` | `_read_state` | 121 | função de serviço sem docstring | `_state_file, file.exists, json.loads, isinstance, file.read_text` |
| `streamer.py` | `_write_state` | 132 | função de serviço sem docstring | `_state_file(state['platform']).write_text, json.dumps, _state_file` |
| `streamer.py` | `_pid_alive` | 141 | função de serviço sem docstring | `os.kill, int` |
| `streamer.py` | `_log` | 153 | função de serviço sem docstring | `list, lines.append, _now, _write_state, level.upper` |
| `streamer.py` | `escape_drawtext` | 165 | Escapa texto para o filtro `drawtext` do FFmpeg. | `value.replace('\\', '\\\\').replace(':', '\\:').replace, out.replace('%', '\\%').replace(',', '\\,').replace('[', '\\[').replace, value.replace('\\', '\\\\').replace, out.replace('%', '\\%').replace(',', '\\,').replace, value.replace` |
| `streamer.py` | `write_playlist` | 171 | Gera o arquivo do demuxer `concat` com os vídeos da fila. | `destination.write_text, str(path.resolve()).replace, lines.append, '\n'.join, str` |
| `streamer.py` | `build_overlay` | 181 | Monta a cadeia de `drawtext` do overlay dinâmico. | `max, options.get, str(options.get('text') or '').strip, int, parts.append` |
| `streamer.py` | `build_command` | 206 | Comando FFmpeg completo da transmissão em loop. | `int, str` |
| `streamer.py` | `parse_stats` | 282 | Extrai fps/bitrate/frames/drop da linha de progresso do FFmpeg. | `_STATS_RE.search, _DROP_RE.search, _SPEED_RE.search, int, float` |
| `streamer.py` | `resolve_target` | 302 | Junta URL base e stream key, respeitando cofre de chaves e env. | `url or ''.strip, key or ''.strip, os.environ.get(spec['env_url']) or spec['default_url'] or ''.strip, os.environ.get(spec['env_key']) or ''.strip, StreamerError` |
| `streamer.py` | `status` | 326 | função de serviço sem docstring | `_read_state, state.get, datetime.fromisoformat, int, _write_state` |
| `streamer.py` | `sessions` | 343 | função de serviço sem docstring | `status` |
| `streamer.py` | `is_running` | 347 | função de serviço sem docstring | `status(platform).get, status` |
| `streamer.py` | `start` | 351 | função de serviço sem docstring | `is_running, resolve_target, write_playlist, _stop_file(platform).unlink, _write_state` |
| `streamer.py` | `stop` | 417 | função de serviço sem docstring | `_read_state, state.get, status, StreamerError, _stop_file(platform).write_text` |
| `streamer.py` | `_stop_requested` | 445 | função de serviço sem docstring | `_stop_file(platform).exists, _stop_file` |
| `streamer.py` | `_supervise` | 449 | função de serviço sem docstring | `build_overlay, build_command, _log, _now, _write_state` |
| `streamer.py` | `iter_output` | 543 | Itera linhas do FFmpeg tratando '\r' — o progresso (-stats) não usa '\n'. | `raw.decode, os.read, buffer.strip, min, stream.fileno` |
| `streamer.py` | `_pump` | 569 | Lê a saída do FFmpeg, alimenta métricas e obedece ao pedido de parada. | `threading.Thread, stop_watch.start, iter_output, proc.wait, stream.close` |
| `streamer.py` | `_kill_on_stop` | 601 | função de serviço sem docstring | `proc.poll, _stop_requested, time.sleep, proc.terminate, proc.wait` |
| `streamer.py` | `reconcile` | 616 | No boot: fecha sessões que ficaram 'no ar' após restart do serviço. | `_read_state, _pid_alive, _now, _write_state, state.get` |
| `transcribe.py` | `dict` | 44 | função de serviço sem docstring | `round` |
| `transcribe.py` | `duration` | 56 | função de serviço sem docstring | `max` |
| `transcribe.py` | `dict` | 59 | função de serviço sem docstring | `round, w.dict` |
| `transcribe.py` | `_providers` | 80 | (rótulo, url, chave) na ordem de preferência. | `api_keys.get_key, out.append, os.environ.get('WHISPER_API_BASE', 'https://api.whisper-api.com').rstrip, Provider, os.environ.get` |
| `transcribe.py` | `available` | 96 | função de serviço sem docstring | `bool, _providers` |
| `transcribe.py` | `missing_key_message` | 100 | função de serviço sem docstring | `` |
| `transcribe.py` | `_multipart` | 111 | função de serviço sem docstring | `fields.items, parts.append, f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file_path.name}"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode, file_path.read_bytes, f'\r\n--{boundary}--\r\n'.encode` |
| `transcribe.py` | `_srt_seconds` | 129 | função de serviço sem docstring | `re.match, map, match.groups` |
| `transcribe.py` | `_payload_from_srt` | 137 | função de serviço sem docstring | `re.split, text.strip, time_line.partition, _srt_seconds, ' '.join(body).strip` |
| `transcribe.py` | `_post_openai` | 171 | função de serviço sem docstring | `_multipart, urllib.request.Request, req.add_header, urllib.request.urlopen, json.loads` |
| `transcribe.py` | `_post_whisper_api` | 204 | função de serviço sem docstring | `_multipart, urllib.request.Request, req.add_header, str(payload.get('task_id') or '').strip, str(payload.get('status') or '').lower` |
| `transcribe.py` | `_extract_mp3` | 278 | função de serviço sem docstring | `media.run, str` |
| `transcribe.py` | `_words_from` | 290 | função de serviço sem docstring | `out.sort, payload.get, str(item.get('word') or item.get('text') or '').strip, out.append, WordStamp` |
| `transcribe.py` | `_segments_from` | 308 | função de serviço sem docstring | `_words_from, payload.get, item.get('text') or ''.strip, out.append, payload.get('text') or ''.strip` |
| `transcribe.py` | `transcribe` | 335 | Devolve (segmentos, idioma detectado). | `_providers, max, work.mkdir, jobs.log, segments.sort` |
| `trends.py` | `_cached` | 35 | função de serviço sem docstring | `time.time, producer, _CACHE.get` |
| `trends.py` | `_snapshot_key` | 47 | função de serviço sem docstring | `(nicho or '').strip().lower, region or 'BR'.upper, nicho or ''.strip` |
| `trends.py` | `_read_snapshot_file` | 51 | função de serviço sem docstring | `_RADAR_SNAPSHOT_FILE.read_text, json.loads, isinstance` |
| `trends.py` | `_write_snapshot_file` | 62 | função de serviço sem docstring | `_RADAR_SNAPSHOT_FILE.parent.mkdir, _RADAR_SNAPSHOT_FILE.write_text, json.dumps` |
| `trends.py` | `load_radar_snapshot` | 67 | função de serviço sem docstring | `_read_snapshot_file, data.get, _snapshot_key, isinstance` |
| `trends.py` | `save_radar_snapshot` | 73 | função de serviço sem docstring | `_read_snapshot_file, _write_snapshot_file, _snapshot_key` |
| `trends.py` | `_http_json` | 79 | função de serviço sem docstring | `urllib.request.Request, req.add_header, headers or {}.items, json.dumps(body).encode, urllib.request.urlopen` |
| `trends.py` | `_http_text` | 92 | função de serviço sem docstring | `urllib.request.Request, urllib.request.urlopen, res.read().decode, res.read` |
| `trends.py` | `_now_iso` | 98 | função de serviço sem docstring | `datetime.now(timezone.utc).isoformat, datetime.now` |
| `trends.py` | `_compact` | 102 | função de serviço sem docstring | `str, f'{value / limit:.1f}'.rstrip('0').rstrip, f'{value / limit:.1f}'.rstrip` |
| `trends.py` | `_normalize_topic` | 143 | função de serviço sem docstring | `' '.join(filtered[:max_words]).strip, w.lower, re.findall, ' '.join, len` |
| `trends.py` | `_topic_words` | 151 | função de serviço sem docstring | `set, _normalize_topic(text).split, _normalize_topic` |
| `trends.py` | `_traffic_value` | 155 | função de serviço sem docstring | `isinstance, re.sub, max, str, int` |
| `trends.py` | `_title_case` | 169 | função de serviço sem docstring | `re.split, ''.join(out).strip, text or ''.strip, chunk.isspace, out.append` |
| `trends.py` | `_score_topic_match` | 183 | função de serviço sem docstring | `_topic_words, len, _normalize_topic, max, topic_norm.split` |
| `trends.py` | `_xml_field` | 207 | função de serviço sem docstring | `re.search, m.group(1).strip() if m else ''.replace, _TAG_RE.pattern.format, m.group(1).strip, m.group` |
| `trends.py` | `google_trends` | 212 | Buscas em alta no país, direto do feed oficial do Google Trends. | `region or 'BR'.upper, _http_text, _ITEM_RE.findall, _xml_field, out.append` |
| `trends.py` | `_ytdlp_json` | 247 | função de serviço sem docstring | `media.run, json.loads, str, isinstance, raw.index` |
| `trends.py` | `_video_from_entry` | 266 | função de serviço sem docstring | `int, entry.get, origin.startswith, _compact, bool` |
| `trends.py` | `_youtube_search` | 292 | função de serviço sem docstring | `re.sub('\\s+', ' ', keyword or '').strip, _ytdlp_json, _video_from_entry, sorted, re.sub` |
| `trends.py` | `youtube_trending` | 304 | Aba oficial de 'Em alta' do YouTube — o que já está viralizando. | `google_trends, set, _ytdlp_json, _video_from_entry, sorted` |
| `trends.py` | `youtube_niche` | 342 | Vídeos recentes do nicho ordenados por tração (views). | `_youtube_search, _ytdlp_json, _video_from_entry, sorted, f'{nicho} {query}'.strip` |
| `trends.py` | `tiktok_niche` | 365 | Virais do TikTok pelo nicho — usa yt-dlp na busca do próprio TikTok | `youtube_niche, re.sub, _ytdlp_json, _video_from_entry, e.get` |
| `trends.py` | `web_signals` | 383 | função de serviço sem docstring | `api_keys.get_key, results.sort, next, time.time, providers.append` |
| `trends.py` | `_evidence_bucket` | 446 | função de serviço sem docstring | `' '.join, _normalize_topic` |
| `trends.py` | `_build_viral_intelligence` | 451 | função de serviço sem docstring | `enumerate, add_video_candidates, candidates.values, ranked.sort, _evidence_bucket` |
| `trends.py` | `add_candidate` | 463 | função de serviço sem docstring | `_evidence_bucket, candidates.setdefault, float, item['sources'].add, item['evidence'].append` |
| `trends.py` | `add_video_candidates` | 521 | função de serviço sem docstring | `enumerate, int, video.get, _normalize_topic, max` |
| `trends.py` | `_llm_json` | 649 | função de serviço sem docstring | `api_keys.rank_providers, list, api_keys.get_key, _http_json, content.find` |
| `trends.py` | `_heuristic_forecast` | 680 | Sem chave de LLM o radar ainda entrega: ranqueia sinais reais coletados. | `out.append, re.sub, t['term'].lower` |
| `trends.py` | `forecast` | 716 | função de serviço sem docstring | `google_trends, youtube_trending, web_signals, _build_viral_intelligence, _PROMPT.format` |
| `trends.py` | `radar` | 796 | função de serviço sem docstring | `_cached, isinstance, load_radar_snapshot, google_trends, youtube_trending` |
| `trends.py` | `build` | 806 | função de serviço sem docstring | `google_trends, youtube_trending, web_signals, _build_viral_intelligence, youtube_niche` |
| `validation.py` | `save_upload` | 25 | função de serviço sem docstring | `secure_filename, Path(name).suffix.lower, config.uploads_dir.mkdir, file.save, jobs.update` |
| `validation.py` | `output_path` | 51 | função de serviço sem docstring | `out_dir.mkdir, config.tool_dir` |
| `validation.py` | `public_url` | 57 | Converte um caminho absoluto no storage em URL relativa de download. | `path.relative_to, rel.as_posix` |
| `validation.py` | `clean_text` | 63 | função de serviço sem docstring | `value or ''.strip, len, ValidationError` |
| `validation.py` | `parse_json_object` | 70 | função de serviço sem docstring | `value or ''.strip, json.loads, isinstance, ValidationError` |
| `video_gen.py` | `dimensions` | 34 | função de serviço sem docstring | `ASPECTS.get` |
| `video_gen.py` | `_narrate` | 38 | função de serviço sem docstring | `dst.with_name, edge_tts.synthesize, voice_forge.filter_chain, media.run, raw.unlink` |
| `video_gen.py` | `_clip_from_image` | 58 | Ken Burns: zoom/pan lento para uma foto virar plano de vídeo. | `max, random.Random, rnd.choice, media.run, int` |
| `video_gen.py` | `_clip_from_video` | 93 | B-roll cortado, enquadrado e mudo (a narração manda no áudio). | `media.run, str` |
| `video_gen.py` | `_concat` | 116 | função de serviço sem docstring | `listing.write_text, media.run, '\n'.join, str, p.as_posix` |
| `video_gen.py` | `_mix_music` | 131 | Trilha em ducking: a música abaixa sozinha quando a narração entra. | `media.run, str` |
| `video_gen.py` | `generate` | 148 | Executa o pipeline completo e entrega o MP4 esterilizado. | `dimensions, workdir.mkdir, random.SystemRandom().randint, enumerate, jobs.check_cancelled` |
| `visuals.py` | `_download` | 46 | função de serviço sem docstring | `urllib.request.Request, req.add_header, headers or {}.items, urllib.request.urlopen, dst.write_bytes` |
| `visuals.py` | `_json` | 59 | função de serviço sem docstring | `urllib.request.Request, req.add_header, headers or {}.items, urllib.request.urlopen, json.loads` |
| `visuals.py` | `pollinations` | 71 | Imagem por IA sem chave e sem limite prático — base do estilo 'canal viral'. | `urllib.parse.urlencode, _download, Asset, urllib.parse.quote` |
| `visuals.py` | `pexels_video` | 81 | função de serviço sem docstring | `api_keys.get_key, urllib.parse.urlencode, _json, VisualError, data.get` |
| `visuals.py` | `pixabay_video` | 104 | função de serviço sem docstring | `api_keys.get_key, urllib.parse.urlencode, _json, VisualError, data.get` |
| `visuals.py` | `premium_video` | 120 | Slot reservado para vídeo por IA pago (Runway/Kling/Veo). | `VisualError` |
| `visuals.py` | `fetch` | 131 | função de serviço sem docstring | `workdir.mkdir, f'{scene.get('visual') or scene.get('narration', '')}. {look_suffix}'.strip, VisualError, scene.get, ' '.join` |
| `visuals.py` | `_kind_of` | 189 | função de serviço sem docstring | `path.suffix.lower` |
| `visuals.py` | `solid_card` | 193 | Último recurso: cartão de cor sólida para o vídeo nunca quebrar no meio. | `random.choice(['#101828', '#1d1b3a', '#232323', '#0f2027']).replace, runner, Asset, random.choice, str` |
| `voice_cloning.py` | `get_provider` | 27 | Retorna o provedor ativo. ElevenLabs se disponível, caso contrário falha (sem motor neural fake). | `voice_engine.available, ElevenLabsCloningProvider` |
| `voice_cloning.py` | `extract_dna` | 34 | Extração auxiliar de metadados acústicos para o provedor local. | `hashlib.sha256(audio_path.read_bytes()).hexdigest, int, get_val, hashlib.sha256, audio_path.read_bytes` |
| `voice_cloning.py` | `get_val` | 37 | função de serviço sem docstring | `int` |
| `voice_cloning.py` | `validate_audio` | 52 | Valida se o áudio atende aos requisitos neurais. | `media.probe, ValueError` |
| `voice_cloning.py` | `preprocess_audio` | 76 | Limpa e normaliza o áudio antes de enviar para o motor neural. | `jobs.log, media.run, str, ','.join` |
| `voice_cloning.py` | `start_cloning_job` | 97 | Executa o fluxo completo de clonagem neural. | `get_provider, ValueError, RuntimeError, jobs.stage, validate_audio` |
| `voice_engine.py` | `payload` | 66 | função de serviço sem docstring | `` |
| `voice_engine.py` | `api_key` | 75 | função de serviço sem docstring | `api_keys.get_key` |
| `voice_engine.py` | `available` | 79 | função de serviço sem docstring | `bool, api_key` |
| `voice_engine.py` | `_request` | 83 | função de serviço sem docstring | `api_key, urllib.request.Request, req.add_header, headers or {}.items, VoiceEngineError` |
| `voice_engine.py` | `_explain` | 105 | função de serviço sem docstring | `body.lower` |
| `voice_engine.py` | `list_voices` | 120 | função de serviço sem docstring | `available, list, _request, json.loads, data.get` |
| `voice_engine.py` | `_silence_points` | 150 | Devolve instantes (s) de silêncio detectados — bons pontos de corte. | `re.finditer, sorted, media.run, jobs.log, points.append` |
| `voice_engine.py` | `plan_cuts` | 174 | Monta as fatias (início, fim) respeitando silêncios quando possível. | `cuts.append, min, abs` |
| `voice_engine.py` | `_slice_audio` | 194 | função de serviço sem docstring | `media.run, VoiceEngineError, str, dst.exists, dst.stat` |
| `voice_engine.py` | `_concat` | 207 | função de serviço sem docstring | `dst.with_suffix, listing.write_text, media.run, listing.unlink, '\n'.join` |
| `voice_engine.py` | `_fit_duration` | 221 | Ajusta a fatia convertida para bater exatamente com a duração original. | `media.probe_duration, max, media.run, src.unlink, src.replace` |
| `voice_engine.py` | `_multipart` | 243 | função de serviço sem docstring | `bytearray, fields.items, f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\nContent-Type: audio/wav\r\n\r\n'.encode, file_path.read_bytes, f'\r\n--{boundary}--\r\n'.encode` |
| `voice_engine.py` | `_persona_to_settings` | 260 | Extrai settings da ElevenLabs a partir de metadados da persona se existirem. | `voice_forge.get, Settings, float, bool, meta.get` |
| `voice_engine.py` | `speech_to_speech` | 274 | função de serviço sem docstring | `media.probe_duration, workdir.mkdir, plan_cuts, jobs.log, enumerate` |
| `voice_engine.py` | `_write_pcm` | 344 | Converte PCM cru 44.1 kHz mono em WAV navegável. | `dst.with_suffix, raw.write_bytes, media.run, raw.unlink, str` |
| `voice_engine.py` | `split_text` | 362 | função de serviço sem docstring | `re.sub, current.strip, text.strip, len, re.findall` |
| `voice_engine.py` | `text_to_speech` | 386 | função de serviço sem docstring | `split_text, workdir.mkdir, jobs.log, enumerate, workdir.glob` |
| `voice_engine.py` | `swap_video_audio` | 446 | função de serviço sem docstring | `media.run, str` |
| `voice_forge.py` | `_clamp` | 39 | função de serviço sem docstring | `max, min, float` |
| `voice_forge.py` | `normalized` | 68 | função de serviço sem docstring | `max, setattr, min, _clamp, int` |
| `voice_forge.py` | `dict` | 74 | função de serviço sem docstring | `asdict` |
| `voice_forge.py` | `_store_path` | 157 | função de serviço sem docstring | `config.config_dir.mkdir` |
| `voice_forge.py` | `_load_raw` | 162 | função de serviço sem docstring | `_store_path, path.exists, json.loads, isinstance, path.read_text` |
| `voice_forge.py` | `_save_raw` | 173 | função de serviço sem docstring | `_store_path, path.with_suffix, tmp.write_text, tmp.replace, json.dumps` |
| `voice_forge.py` | `_from_dict` | 180 | função de serviço sem docstring | `clean.setdefault, Persona(**clean).normalized, slugify, Persona, raw.items` |
| `voice_forge.py` | `bootstrap` | 192 | Garante que as personas de fábrica existam e estejam atualizadas no cofre local. | `_load_raw, str, data.get, _from_dict(dict(preset)).dict, _save_raw` |
| `voice_forge.py` | `reset_factory_presets` | 226 | Recria as personas de fábrica do zero, descartando versões antigas. | `_load_raw, _save_raw, _from_dict(dict(preset)).dict, str, _from_dict` |
| `voice_forge.py` | `list_personas` | 235 | função de serviço sem docstring | `bootstrap, personas.sort, _load_raw, _from_dict(raw).dict, data.values` |
| `voice_forge.py` | `get` | 244 | função de serviço sem docstring | `bootstrap, _load_raw().get, _from_dict, _load_raw` |
| `voice_forge.py` | `slugify` | 251 | função de serviço sem docstring | `re.sub('[^a-z0-9]+', '_', name.strip().lower()).strip, re.sub, name.strip().lower, name.strip` |
| `voice_forge.py` | `save` | 256 | função de serviço sem docstring | `_from_dict, persona.name.strip, ValueError, slugify, _load_raw` |
| `voice_forge.py` | `delete` | 279 | função de serviço sem docstring | `_load_raw, data.pop, _save_raw` |
| `voice_forge.py` | `_noise` | 317 | Ruído determinístico em [-1, 1] com o tamanho pedido. | `len, hashlib.sha256(f'{seed}#{counter}'.encode('utf-8')).digest, out.extend, hashlib.sha256, f'{seed}#{counter}'.encode` |
| `voice_forge.py` | `generate_variants` | 328 | Deriva `count` modelos distintos a partir de uma voz base. | `max, _noise, range, min, Persona(id=slugify(label), name=label, base_voice=pool[index % len(pool)], engine=base.engine, pitch=base.pitch + float(arch['pitch']) * intensity + n[0] * 0.8 * intensity, formant=base.formant + float(arch['formant']) * intensity + n[1] * 0.02 * intensity, warmth=base.warmth + float(arch['warmth']) * intensity + n[2] * 1.0 * intensity, brightness=base.brightness + float(arch['brightness']) * intensity + n[3] * 1.0 * intensity, breath=base.breath + float(arch['breath']) * intensity + n[4] * 0.06 * intensity, body=base.body + float(arch['body']) * intensity + n[5] * 0.8 * intensity, room=base.room + float(arch['room']) * intensity + n[6] * 0.05 * intensity, tempo=base.tempo + float(arch['tempo']) * intensity + n[7] * 0.015 * intensity, rate=int(round(base.rate + float(arch['rate']) * intensity + n[8] * 3 * intensity)), notes=f'Modelo {arch['label'].lower()} derivado de “{base.name or base.base_voice}”.').normalized` |
| `voice_forge.py` | `save_many` | 375 | função de serviço sem docstring | `payload.pop, saved.append, isinstance, item.dict, dict` |
| `voice_forge.py` | `dna` | 387 | Sequência determinística em [-1, 1] derivada do id da persona. | `hashlib.sha256(persona_id.encode('utf-8')).digest, hashlib.sha256, persona_id.encode` |
| `voice_forge.py` | `filter_chain` | 394 | Cadeia FFmpeg que transforma a voz base na persona. | `persona.normalized, dna, _atempo_steps, chain.append, min` |
| `voice_forge.py` | `_atempo_steps` | 457 | `atempo` só aceita 0.5–2.0; encadeia quando o fator extrapola. | `max, min, steps.append, abs` |

## Rotas frontend e endpoints literais

| Arquivo | Endpoints detectados |
|---|---|
| `src/routes/__root.tsx` | — |
| `src/routes/apis.tsx` | `/api/apis`, `/api/apis</code>.` |
| `src/routes/canva-cleaner.tsx` | `/api/canva-cleaner/run` |
| `src/routes/conta.tsx` | — |
| `src/routes/estudio.tsx` | `/api/studio/options`, `/api/studio/run`, `/api/studio/storyboard` |
| `src/routes/historico.$jobId.tsx` | `/api/jobs/${jobId}`, `/api/jobs/${jobId}/cancel` |
| `src/routes/historico.tsx` | — |
| `src/routes/index.tsx` | `/api/youtube/bypass` |
| `src/routes/legendar.tsx` | — |
| `src/routes/live-tiktok.tsx` | — |
| `src/routes/live-youtube.tsx` | — |
| `src/routes/login.tsx` | — |
| `src/routes/radar.tsx` | `/api/radar` |
| `src/routes/recap.tsx` | `/api/recap/run` |
| `src/routes/tiktok.tsx` | `/api/tiktok`, `/api/tiktok/clone`, `/api/tiktok/trends?nicho` |
| `src/routes/voice-conversion.tsx` | — |

## Critério de leitura

Funções decoradas com `@bp.get`, `@bp.post`, `@bp.put`, `@bp.patch` ou `@bp.delete` formam a superfície HTTP. Funções sem decorator são helpers de validação, transformação, persistência ou workers. O inventário não prova que uma função foi exercitada em produção; a disponibilidade publicada deve ser conferida no relatório funcional e no snapshot de produção.
