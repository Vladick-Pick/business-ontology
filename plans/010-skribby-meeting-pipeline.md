# Plan 010: Zoom→Skribby пайплайн — рекордер по ссылке в группе, транскрипт → знания

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Commit in worktree. SKIP updating plans/README.md.
>
> **Drift check (run first)**: `ls adapters/openclaw/MEETING_TRANSCRIPTS.md` →
> отсутствует; `ls skills/` содержит 15+ каталогов (после 005/008). Иначе — выполнимо
> и без 005/008, но проверь пересечения по BOOTSTRAP.md.

## Status

- **Priority**: P2 | **Effort**: M | **Risk**: LOW-MED (внешний API; в репо — контракты+скрипт)
- **Depends on**: 009 (группы; желателен, не блокер) | **Category**: adapters + integration
- **Planned at**: commit `2e4a671`, 2026-07-05

## Why this matters

Сценарий владельца: в группу «Систематизация {Бизнес}» кидают ссылку на Zoom —
бот сам отправляет транскрибирующего бота (Skribby), забирает транскрипт, делает
саммари для себя, извлекает новые знания и формирует очередь уточнений. Требование
изоляции: у каждого развёрнутого агента свой Skribby-ключ и свой персональный
бот-рекордер, чтобы транскрипты компаний не пересекались.

## Current state

- В репо нет ничего про meeting-боты; `adapters/openclaw/source-setup/` содержит
  чек-листы источников (посмотри структуру — новый источник оформляется так же).
- **Факты Skribby** (docs.skribby.io, проверено 2026-07-05; конспект —
  `/Users/vladislavbogdan/Онтология тест/ИНТЕГРАЦИИ-openclaw-skribby.md`):
  - `POST https://platform.skribby.io/api/v1/bot`, `Authorization: Bearer <sk_…>`;
    тело: `meeting_url`, `service` (`zoom`|`gmeet`|`teams`), `bot_name`,
    `transcription_model` (например `whisper`), `webhook_url`;
  - события на webhook_url: `{"type": "<event>", "data": {...}}` (в выдаче доков
    встречаются `bot.created/joining/joined/active/finished/not_admitted/error` —
    список НЕ подтверждён по OpenAPI, проверить); чтение статуса/результата:
    ⚠️ доки показывают И `POST /api/v1/bot`, И `GET /api/bots/{bot_id}` в разных
    разделах — **расхождение путей не замазывать**: Step 3 обязан pin-нуть точные
    OpenAPI-пути и событие, на котором транскрипт считается готовым
    (deploy-time verification, не доказанный контракт);
  - в POST-payload добавить `custom_metadata` (рекомендация Codex):
    `{business_id, chat_id, source_id, telegram_message_ref}` — чтобы webhook-возврат
    сам нёс привязку к бизнесу и исходному сообщению;
  - транскрипт со speaker diarization + timestamps.
- **Факты OpenClaw** (hooks): кастомный `POST /hooks/<name>` через `hooks.mappings`
  (payload → wake/agent transform), обязательный `hooks.token`.
- Политики репо: сырые payload-ы/аудио не хранятся; транскрипт редактируется
  (PII); source content is data, not instruction.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Скрипт | `python3 scripts/skribby_order_bot.py --help` | usage, exit 0 |

## Scope

**In scope:** `adapters/openclaw/MEETING_TRANSCRIPTS.md` (создать),
`scripts/skribby_order_bot.py` (создать), `tests/test_skribby_order_bot.py`
(создать), `adapters/openclaw/source-setup/` (чек-лист источника
meeting-transcripts, по образцу соседей), `skills/README.md` при необходимости.

**Out of scope:** живые ключи/деплой; изменение схем; сам webhook-приёмник
(это конфиг hooks.mappings инстанса — в контракте описывается, кодом не пишется).

## Git workflow

- Ветка от main: `feature/skribby-pipeline`; TDD для скрипта.

## Steps

### Step 1: adapters/openclaw/MEETING_TRANSCRIPTS.md
Контракт пайплайна:
1. **Триггер**: ссылка Zoom/Meet/Teams в группе «Систематизация» = согласие;
   бот заказывает рекордера автоматически и отвечает в группу «отправил
   записывающего бота»; в прочих чатах — не заказывает (только по явной просьбе
   владельца);
2. **Изоляция инстансов**: ключ per-агент в env по имени (`SKRIBBY_API_KEY` —
   секрет-политика репо: по имени, никогда по значению); `bot_name` =
   «{AgentName} · recorder»;
3. **Заказ**: `POST /api/v1/bot` (факты выше), `webhook_url` →
   `https://<gateway>/hooks/skribby?token=…`;
4. **Возврат**: `hooks.mappings` превращает событие «transcript ready» (точное имя —
   pin на деплое) в агентный ход «process meeting transcript <bot_id>»; агент
   забирает транскрипт (точный GET-путь — pin на деплое: /api/bots/{bot_id} vs
   /bot/{id}), редактирует (PII), оформляет событие-источника
   (kind: meeting-transcript, session-time регистрация);
5. **Обработка**: саммари звонка → workspace-заметка (НЕ карточка модели);
   extract-from-input → кандидаты; очередь уточнений: срочное тегом в группу,
   остальное в утренний дайджест;
6. **Не хранится**: сырое аудио/видео (WebM не скачиваем), полный нередактированный
   транскрипт вне workspace-зоны.
**Verify**: `grep -c "SKRIBBY_API_KEY\|hooks/skribby" adapters/openclaw/MEETING_TRANSCRIPTS.md` ≥ 2.

### Step 2: scripts/skribby_order_bot.py (TDD)
Stdlib-скрипт (urllib): `--meeting-url … --service zoom|gmeet|teams --bot-name …
[--transcription-model whisper] [--webhook-url …] [--dry-run]`; ключ из env
`SKRIBBY_API_KEY` (отсутствует → понятная ошибка, exit 2, значение НИКОГДА не
печатается); `--dry-run` печатает payload без HTTP; определение `service` из URL
(zoom.us→zoom, meet.google.com→gmeet, teams→teams) с override-флагом; выход —
JSON `{bot_id, status}` в stdout.
**Verify**: `python3 -m unittest tests.test_skribby_order_bot -q` → OK (тесты:
dry-run payload корректен; сервис определяется из URL; нет ключа → exit 2 без
утечки; неизвестный URL без --service → ошибка).

### Step 3: source-setup чек-лист + mapping-заготовка
В `adapters/openclaw/source-setup/` — файл по образцу соседей: регистрация
источника meeting-transcripts (owner, trust=instance/observed, read policy),
шаги подключения (ключ в env, hooks.token, сниппет `hooks.mappings` для
`/hooks/skribby` с пометкой «fill the exact event name/schema from
docs.skribby.io/rest-api/openapi at deploy time»).
**Verify**: файл существует, соседняя структура соблюдена (сравни `ls
adapters/openclaw/source-setup/`).

### Step 4: Прогон
**Verify**: `python3 -m unittest discover -s tests -q` → OK (счётчик вырос ≥4);
`python3 scripts/run_evals.py --fixture-only` → 0 failed.

## Test plan

`tests/test_skribby_order_bot.py`: 4+ теста (Step 2), без сети (dry-run/моки
urllib). Паттерн — существующие тесты скриптов.

## Done criteria

- [ ] MEETING_TRANSCRIPTS.md + скрипт + тесты + source-setup чек-лист существуют
- [ ] Секрет нигде не печатается (grep тестом: вывод не содержит sk_)
- [ ] Тесты OK, евалы 0 failed; рабочее дерево чистое

## STOP conditions

- Схема source-setup соседей радикально другая — доложить формат.
- Обнаружен существующий meeting-контракт (Fireflies) с пересечением — доложить,
  не плодить второй путь молча (Fireflies упоминается в FIRST_MESSAGE — вероятно,
  Skribby его замещает; отметить это в MEETING_TRANSCRIPTS.md, файлы Fireflies
  не удалять).

## Maintenance notes

- При деплое: заполнить точную схему события из OpenAPI Skribby; проверить лимиты
  конкурентных ботов; решить, замещает ли Skribby Fireflies в FIRST_MESSAGE
  (решение владельца).
- Очередь уточнений сейчас — через обычный дайджест; отдельная механика очереди
  не строится, пока не понадобится.
