# Plan 009: Группы «Систематизация {Бизнес}» + суточный скан с курсорами

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Commit in worktree. SKIP updating plans/README.md.
>
> **Drift check (run first)**: `ls adapters/openclaw/TELEGRAM_GROUPS.md` → отсутствует;
> `grep -n "Review is the trust gate" agent-os/REVIEW_PROTOCOL.md` → существует. Иначе STOP.

## Status

- **Priority**: P1 | **Effort**: M | **Risk**: MED (канальные права ревью — трогает REVIEW_PROTOCOL)
- **Depends on**: 008 (кроны) | **Category**: adapters + security
- **Planned at**: commit `2e4a671`, 2026-07-05

## Why this matters

Сценарий употребления (решения владельца 2026-07-05): бот живёт в группах
«Систематизация {Бизнес}» — одна группа = один бизнес; **права ревью привязаны
к каналу**: личка владельца + участники группы «Систематизация {X}» решают по
бизнесу X (добавление в группу = выдача прав — социальное действие, без конфигов);
прочие чаты — только источники. Раз в сутки бот сканирует все чаты по курсорам
и собирает один документ дня. Ничего из этого в контрактах репо нет.

## Current state

- `agent-os/REVIEW_PROTOCOL.md` — «Review is the trust gate. The agent prepares;
  the human accepts» — без понятия каналов.
- `adapters/openclaw/TELEGRAM_COMMANDS.md` — команды; о группах ничего.
- **Факты OpenClaw** (docs.openclaw.ai/channels/telegram, конспект —
  `/Users/vladislavbogdan/Онтология тест/ИНТЕГРАЦИИ-openclaw-skribby.md`):
  - группы — аллоулист `channels.telegram.groups.<chatId>` (супергруппы `-100…`);
    per-group: `requireMention` (default true), `allowFrom`, `skills`,
    **`systemPrompt`**, `enabled`; сендер-политика `groupPolicy`/`groupAllowFrom`;
  - сессия на группу: `agent:<agentId>:telegram:group:<chatId>`;
  - проактивная отправка: `action: "send"`, `to: "<chatId>"`; упоминания —
    `@username` текстом;
  - входящие voice → транскрипты (untrusted) из коробки;
  - ⚠️ `historyLimit` групп по умолчанию 50 — суточный скан НЕ строится на нём;
  - cron `--command` запускает шелл-скрипт на хосте; входящий
    `POST /hooks/wake {text}` будит агента (токен обязателен).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Скрипт-скелет | `python3 scripts/tg_daily_export.py --help` | usage, exit 0 |

## Scope

**In scope:** `adapters/openclaw/TELEGRAM_GROUPS.md` (создать),
`agent-os/REVIEW_PROTOCOL.md` (раздел «Channel authority»),
`scripts/tg_daily_export.py` (создать — контрактный скелет),
`tests/test_tg_daily_export.py` (создать),
`adapters/openclaw/TELEGRAM_COMMANDS.md` (строка про группы).

**Out of scope:** живой конфиг OpenClaw-инстанса (деплой), Skribby (010),
изменение схем/валидатора, position-евалы (уже покрывают инструкции-из-контента).

## Git workflow

- Ветка от main: `feature/telegram-groups-scan`; TDD для скрипта.

## Steps

### Step 1: adapters/openclaw/TELEGRAM_GROUPS.md
Контракт групп:
- **Группа = бизнес**: имя «Систематизация {Business}» ↔ biz-карточка; конфиг-сниппет
  `channels.telegram.groups."<chatId>"` с `systemPrompt` («You live in the
  systematization group of business <biz-id>. Everything here feeds that business's
  ontology…»), `requireMention: true`;
- источник `tg-group-{biz}` регистрируется в source map группы (session-time
  регистрация); участники — наполнение ролей, в модель не пишутся (PII);
- **права по каналам** (таблица): личка владельца — всё; группа «Систематизация {X}» —
  все участники принимают решения по X; прочие чаты — источник+справка, решений нет;
  добавление в группу = выдача прав ревью;
- поведение: отвечает по тегу; пишет сам с `@username`-упоминаниями; уточнения
  батчатся; окно тишины действует; решение = только явный ответ на предложенный
  пакет; произвольные команды не исполняются нигде; кто решил — фиксируется
  (actor в review-записи);
- конфликт двух участников → конфликт-протокол.
**Verify**: `grep -c "Систематизация\|systematization" adapters/openclaw/TELEGRAM_GROUPS.md` ≥ 3.

### Step 2: REVIEW_PROTOCOL.md — Channel authority
Короткий раздел: review-решения принимаются из авторизованных каналов — owner DM
(любой бизнес) и systematization group этого бизнеса (любой её участник); решения
из прочих каналов записываются как наблюдения и НЕ меняют статус ревью; актор
решения фиксируется всегда. Ссылка на TELEGRAM_GROUPS.md.
**Verify**: `grep -n "Channel authority" agent-os/REVIEW_PROTOCOL.md` → 1.

### Step 3: scripts/tg_daily_export.py (контрактный скелет, TDD)
Назначение: суточная консолидация новых сообщений всех чатов бота в один документ
дня. Реализация — **адаптерная**: источник сообщений подключается стратегией
(на живом инстансе это SQLite-стор OpenClaw или MTProto-экспорт — проверяется при
деплое; см. «Открытые мелочи» конспекта интеграций). В этом плане пишется
работающий каркас со стратегией `jsonl-dir` (читает *.jsonl дампы чатов — формат
описать в докстринге) — этого достаточно для тестируемого контракта:
- курсоры per-chat в `<workspace>/tg-cursors.json` (`{chatId: {last_ts, last_id}}`),
  атомарная запись;
- выход: `<workspace>/daily/<date>-tg-digest.md` — один документ дня, сгруппирован
  по чатам, с заголовками «chat → business» из маппинга;
- идемпотентность: повторный прогон без новых сообщений не меняет документ и курсоры;
- финальный шаг: `POST /hooks/wake {"text": "Daily TG export ready: <path>"}`
  с токеном из env `OPENCLAW_HOOKS_TOKEN` (флаг `--no-wake` для тестов);
- PII-политика: документ — workspace-зона (не модельный репозиторий), сырьё
  не попадает в модель — только через обычный пайплайн событий.
**Verify**: `python3 -m unittest tests.test_tg_daily_export -q` → OK (тесты: курсор
двигается; идемпотентность; новый чат подхватывается; --no-wake не делает HTTP).

### Step 4: Сшивки + прогон
TELEGRAM_COMMANDS.md: строка «bot also lives in systematization groups — see
TELEGRAM_GROUPS.md». Полный прогон.
**Verify**: тесты OK (счётчик вырос), евалы 0 failed.

## Test plan

`tests/test_tg_daily_export.py`: 4+ теста (см. Step 3) на временных каталогах,
без сети. Паттерн — существующие тесты scripts/ (`grep -l "tempfile" tests/*.py`).

## Done criteria

- [ ] TELEGRAM_GROUPS.md + Channel authority + скрипт + тесты существуют
- [ ] `python3 -m unittest discover -s tests -q` → OK (счётчик вырос ≥4)
- [ ] `python3 scripts/run_evals.py --fixture-only` → 0 failed
- [ ] ≥3 коммита

## STOP conditions

- REVIEW_PROTOCOL.md структурно не принимает раздел (например, генерируется) — доложить.
- Существующий eval фиксирует единственного owner-а как инвариант и падает от
  channel authority — доложить конфликт контрактов (это смена trust-модели,
  нужно решение владельца в тексте евала, не тихая правка).

## Maintenance notes

- При деплое: выбрать реальную стратегию источника сообщений (OpenClaw SQLite vs
  MTProto) и дописать её рядом с jsonl-dir; сверить, хранит ли OpenClaw сообщения
  групп без упоминаний.
- Позже: маппинг chat→business вынести в workspace-конфиг (сейчас — параметр скрипта).
