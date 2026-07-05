# Plan 009 (v2, переписан 2026-07-05): Группы «Систематизация {Бизнес}» + folder-first суточный инжест по образцу «ИИ Богдан»

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Commit in worktree. SKIP updating plans/README.md.
>
> **Drift check (run first)**: `ls adapters/openclaw/TELEGRAM_GROUPS.md` → отсутствует;
> `grep -n "Review is the trust gate" agent-os/REVIEW_PROTOCOL.md` → существует. Иначе STOP.

## Status

- **Priority**: P1 | **Effort**: L | **Risk**: MED (канальные права — trust-модель)
- **Depends on**: 008 (кроны) | **Category**: adapters + security + agent-harness
- **Planned at**: commit `c53bb14`, 2026-07-05
- **Заменяет**: v1. Две поправки: (1) по ревью Codex — high-risk решения НЕ отдаются
  всей группе; (2) по решению владельца — суточный инжест строится **folder-first
  по образцу работающего прецедента «ИИ Богдан»**
  (`/Users/vladislavbogdan/Documents/ИИ Богдан/openclaw-migration/server-current/workspace/skills/telegram-daily-ingest/SKILL.md`):
  Python-коллектор — только экстрактор данных, семантику интерпретирует агент;
  live MTProto/OpenClaw-адаптер — ТОЛЬКО после живого доказательства.

## Why this matters

Сценарий владельца: бот живёт в группах «Систематизация {Бизнес}» (одна группа =
один бизнес), права ревью привязаны к каналу, раз в сутки все чаты сканируются
в один документ дня. Прецедент «ИИ Богдан» уже доказал рабочую архитектуру
инжеста (collector JSON → LLM interpretation → durable summary → digest) — её
и переносим, вместо изобретения своей.

## Current state

- `agent-os/REVIEW_PROTOCOL.md` — «Review is the trust gate…», каналов нет.
- `specs/REVIEW-SPEC.md:68` — source-of-truth/authority уже верхний impact-tier,
  но без привязки к каналам/ролям.
- **Прецедент ИИ Богдан** (ключевые правила, портировать дословно по смыслу):
  «The Python collector/wrapper is a data extractor only; it must not be treated
  as the semantic interpreter»; «Do not outsource semantic interpretation to
  regex/script output»; «Task handling is state understanding, not extraction»;
  «Do not invent tasks if the evidence is weak»; bare-mention недостаточно;
  закрытые треды резолвятся по поздним сообщениям. Артефакты коллектора:
  `run_manifest.json` + per-chat manifests + attachments + interpretation packet.
- **Факты OpenClaw** (конспект `/Users/vladislavbogdan/Онтология тест/ИНТЕГРАЦИИ-openclaw-skribby.md`):
  группы-аллоулист `channels.telegram.groups.<chatId>` с per-group `systemPrompt`,
  `requireMention`; сессия на группу; voice → транскрипты; cron `--command`;
  `POST /hooks/wake`; ⚠️ `historyLimit` 50 — суточный скан на нём НЕ строится.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Коллектор | `python3 scripts/tg_collect_daily.py --help` | usage, exit 0 |

## Scope

**In scope:** `adapters/openclaw/TELEGRAM_GROUPS.md` (создать),
`agent-os/REVIEW_PROTOCOL.md` (раздел Channel authority),
`scripts/tg_collect_daily.py` + `tests/test_tg_collect_daily.py` (создать),
`skills/daily-ingest/SKILL.md` (создать — агентная интерпретация пакета),
`adapters/openclaw/source-setup/` (вопросник настройки TG-скана),
`adapters/openclaw/TELEGRAM_COMMANDS.md` (строка про группы), `skills/README.md`.

**Out of scope:** живой MTProto/OpenClaw-адаптер чтения сообщений (ТОЛЬКО после
живого теста — см. Maintenance), живые ключи/деплой, схемы/валидатор.

## Git workflow

- Ветка от main: `feature/groups-daily-ingest`; TDD для коллектора.

## Steps

### Step 1: TELEGRAM_GROUPS.md — группы и канальные права
Контракт групп (как в v1: группа=бизнес через per-group systemPrompt; источник
`tg-group-{biz}`; участники — наполнение ролей, в модель не пишутся; поведение:
по тегу, проактивные @упоминания, батчинг, окно тишины; решение = только явный
ответ на пакет; актор фиксируется; конфликт участников → конфликт-протокол)
**плюс градация по риску (поправка Codex):**

| Решение | Кто может |
|---|---|
| Обычные изменения бизнеса X | владелец (личка) + любой участник группы «Систематизация {X}» |
| **High-risk** (source-of-truth, authority/полномочия, measurement-convention — верхний tier из specs/REVIEW-SPEC.md) | **только владелец в личке** (по умолчанию; владелец может явно расширить) |

**Verify**: `grep -c "high-risk\|High-risk" adapters/openclaw/TELEGRAM_GROUPS.md` ≥ 2.

### Step 2: REVIEW_PROTOCOL.md — Channel authority
Раздел: авторизованные каналы решений (owner DM — всё; systematization group —
не-high-risk по своему бизнесу; прочие каналы — решения не принимаются,
фиксируются как наблюдения); high-risk дефолт — owner DM only; актор всегда
фиксируется. Ссылка на TELEGRAM_GROUPS.md.
**Verify**: `grep -n "Channel authority" agent-os/REVIEW_PROTOCOL.md` → 1.

### Step 3: Коллектор tg_collect_daily.py (TDD) — данные, НЕ смысл
По образцу ИИ Богдан, stdlib: вход — **папка экспортов чатов** (`--exports-dir`;
формат 1: Telegram Desktop JSON export `result.json`; формат 2: `*.jsonl` дампы —
оба описать в докстринге), `--cursors-file` (per-chat `{last_ts,last_id}`,
атомарная запись), `--out-dir`, `--chat-map` (chatId/slug → business), `--tz`,
`--backfill-days`, `--no-wake`. Выход за прогон:
`run_manifest.json` (что обработано, счётчики, окно), per-chat `chat_manifest.json`,
`interpretation_packet.json` (нормализованные сообщения: chat, sender-роль/slug
без телефонов, ts, text, reply_to, attachments-ссылки) — **никакой интерпретации,
никаких regex-«задач»**. Идемпотентность: повтор без новых сообщений → no-op.
Финал: `POST /hooks/wake {"text": "Daily ingest packet ready: <path>"}`
(токен из env `OPENCLAW_HOOKS_TOKEN`; `--no-wake` для тестов). Выход — workspace-зона.
**Verify**: `python3 -m unittest tests.test_tg_collect_daily -q` → OK (тесты:
курсор двигается; идемпотентность; оба формата; новый чат подхватывается;
packet не содержит полей phone/email; --no-wake без HTTP).

### Step 4: skills/daily-ingest/SKILL.md — агентная интерпретация
По структуре соседних скиллов + правила из прецедента, адаптированные под
онтологию: читать packet как structured evidence only; резолвить поздние ответы
и закрытые треды ДО выводов; мержить дубли между чатами; классифицировать
последствия (кандидат изменения модели / дрейф / конфликт источников / фиксация
source-of-truth / уточнение к людям / шум-no-op); голосовые транскрипты — в тот же
проход; «не выдумывай изменения из слабых свидетельств»; bare-mention ≠ сигнал;
выход — обычные события-источники + model-change пакеты через propose-change +
очередь уточнений в дайджест; компактная сводка дня. Права каналов учитываются
(Step 1-2): ответы из групп = claims, решения — по таблице.
**Verify**: файл существует; `grep -c "structured evidence\|not the semantic" skills/daily-ingest/SKILL.md` ≥ 1.

### Step 5: Вопросник настройки (агент спрашивает сам, секреты — только именами)
`adapters/openclaw/source-setup/telegram-scan.md` по образцу соседей: агент
выясняет — режим источника (folder-export | OpenClaw stored events | MTProto
user session); путь к папке экспортов, формат, timezone, backfill window;
список чатов/групп + маппинг chat→business; скоуп (все сообщения / только
mentions / выбранные топики); куда писать курсоры/выход (вне модельного репо);
правила редакции PII; расписание и канал ревью; **секреты — ТОЛЬКО именами env**
(`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_PATH`,
`OPENCLAW_HOOKS_TOKEN`) — значения в чат не запрашиваются никогда.
**Verify**: `grep -c "TELEGRAM_API_ID" adapters/openclaw/source-setup/telegram-scan.md` → ≥1;
`grep -ci "never.*value\|не.*значени" …` ≥ 1 (формулировка запрета значений).

### Step 6: Сшивки + прогон
TELEGRAM_COMMANDS.md — строка про группы; skills/README.md — daily-ingest.
**Verify**: тесты OK (счётчик вырос), евалы 0 failed.

## Test plan
Тесты коллектора (Step 3, 6+), без сети. Поведенческие кейсы daily-ingest —
в SKILL.md (2 кейса: закрытый тред не поднимается как изменение; слабое
свидетельство → уточнение, не кандидат).

## Done criteria

- [ ] TELEGRAM_GROUPS.md (с high-risk градацией) + Channel authority + коллектор
      + skills/daily-ingest + вопросник существуют
- [ ] Коллектор не содержит семантики (нет «task», «decision»-эвристик — grep)
- [ ] Тесты OK (≥6 новых), евалы 0 failed; рабочее дерево чистое; артефакты коллектора из Step 3 (run_manifest/chat_manifest/packet) воспроизводимы на тестовых данных

## STOP conditions

- Существующий eval фиксирует единственного owner-а и падает от Channel authority —
  доложить (смена trust-модели требует правки текста евала решением, не тихо).
- Формат Telegram Desktop export не парсится stdlib-ом в 2 форматах — доложить,
  сузить до jsonl.

## Maintenance notes

- **Live-адаптер (MTProto / OpenClaw store) — отдельный шаг после живого теста**
  на сервере: сначала доказать, что источник реально видит unmentioned-сообщения
  групп; folder-first работает уже сейчас без телеграм-авторизации.
- Прецедент ИИ Богдан включает транскрипцию вложений и календарь-кросс-чек —
  сюда не переносить, пока не понадобится (у резидента другой контур).
