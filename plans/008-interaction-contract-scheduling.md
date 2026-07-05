# Plan 008: Ритм и кроны — скилл interaction-contract + adapters/openclaw/SCHEDULING.md

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Commit in worktree. SKIP updating plans/README.md.
>
> **Drift check (run first)**: `ls adapters/openclaw/SCHEDULING.md` → должен
> отсутствовать; `ls skills/interaction-contract` → должен отсутствовать. Иначе STOP.

## Status

- **Priority**: P1 | **Effort**: M | **Risk**: LOW | **Depends on**: 005 (playbook ссылается сюда)
- **Category**: dx + adapters | **Planned at**: commit `2e4a671`, 2026-07-05

## Why this matters

Договор о взаимодействии (ритм дайджестов, окно тишины, каналы) — **рантайм-конфиг
агента, НЕ карточка модели** (жёсткое решение владельца: «настройки агента живут
в рантайме и настраиваются оттуда»). Сейчас в репо нет ни контракта самопланирования
(только абстрактное «On each scheduled run» в OPERATING_LOOP), ни места, где договор
записан. OpenClaw даёт всё необходимое из коробки — нужно только зафиксировать
контракт и научить агента им пользоваться.

## Current state

- `agent-os/OPERATING_LOOP.md:32` — «On each scheduled run:» — единственное
  упоминание расписаний.
- `templates/workspace/` — 5 шаблонов (SOUL, COMMUNICATION_POLICY, REVIEW_PROTOCOL,
  TELEGRAM_COMMANDS, HUMAN_README); INTERACTION_CONTRACT нет.
- Скилла `interaction-contract` нет (13 существующих — `ls skills/`).
- **Факты OpenClaw** (проверено по docs.openclaw.ai/automation/cron-jobs,
  2026-07-05; полный конспект — `/Users/vladislavbogdan/Онтология тест/ИНТЕГРАЦИИ-openclaw-skribby.md`):
  - `openclaw cron create "<name>" --cron "0 9 * * *" --tz <IANA> --session
    isolated|main|current --message "…"|--command "…"|--system-event "…"`;
    интервалы `--every 1d`, разовые `--at`.
  - Доставка: `--announce --channel telegram --to "<chatId>"` ЛИБО `--webhook <url>`
    (несовместимы). Хранение — общий SQLite (рестарты переживает). У агента есть
    cron-тул (list/get).
  - Таймзоны: без `--tz` крон-выражения идут в таймзоне хоста.

**Решения владельца (нормативно, 2026-07-02/05):** дефолт — «раз в день»
(один дайджест 09:00); срочной полосы нет — high-risk топ-строкой дайджеста
(безопасно: непринятое не действует); окно тишины 22:00–09:00 одностороннее
(сам не пишет, на входящие отвечает); текст — Telegram, визуал — вьюер на сервере;
ритм меняется фразой в чате без ревью-ворот.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |

## Scope

**In scope:** `adapters/openclaw/SCHEDULING.md` (создать),
`skills/interaction-contract/SKILL.md` (создать),
`templates/workspace/INTERACTION_CONTRACT.md.tpl` (создать),
`agent-os/OPERATING_LOOP.md` (одна вставка: расписание берётся из
INTERACTION_CONTRACT), `skills/README.md`, `adapters/openclaw/BOOTSTRAP.md`
(шаг после онбординга: установить кроны по договору).

**Out of scope:** сами скрипты сканов (план 009), Skribby (010), TELEGRAM_COMMANDS
(команды типа /rhythm — отложить: смена ритма работает обычной фразой).

## Git workflow

- Ветка от main: `feature/interaction-scheduling`; коммит на шаг.

## Steps

### Step 1: templates/workspace/INTERACTION_CONTRACT.md.tpl
Шаблон рантайм-конфига (workspace-зона, рядом с SOURCES.md): rhythm
(immediate|daily|weekly; default daily), digest time (09:00), quiet window
(22:00–09:00, one-way: no outbound, inbound answered), channels (text: Telegram
DM владельца; visuals: server viewer URL), последняя человекочитаемая строка-зеркало
кронов («scan nightly 03:00, digest 09:00, silent after 22:00»). Явная шапка:
«Agent runtime configuration. NOT part of the company model. Changed by the human
in chat at any time; the agent confirms and reschedules its cron jobs.»
**Verify**: файл существует; `grep -c "NOT part of the company model" templates/workspace/INTERACTION_CONTRACT.md.tpl` → 1.

### Step 2: adapters/openclaw/SCHEDULING.md
Контракт самопланирования с фактическим CLI (из Current state, с оговоркой
«сверь `openclaw cron --help` на живом инстансе — синтаксис между версиями
менялся»). Три профиля:
- **daily (default)**: `openclaw cron create "tg-daily-export" --cron "0 3 * * *"
  --tz <owner tz> --session isolated --command "<export script, план 009>"`;
  `"sources-scan" --cron "30 3 * * *"` (GDrive delta, дашборды);
  `"morning-digest" --cron "0 9 * * *" --session main --message "Prepare and send
  the daily digest per INTERACTION_CONTRACT" --announce --channel telegram --to
  "<owner chatId>"`; `"drift-sweep" --cron "0 4 * * 0"`; `"model-health"
  --cron "0 9 1 * *"`.
- **immediate**: сканы каждые 2–4 ч рабочего окна + вечерняя сводка.
- **weekly**: ночные сканы ежедневно, длинный дайджест пн 10:00.
Правила: окно тишины — не ставить исходящие кроны в 22–09 (кроме безмолвных
--command сканов); смена ритма = переписать кроны + обновить INTERACTION_CONTRACT.md;
каждый scheduled run начинается с Re-anchor (ссылка на Position recovery).
**Verify**: `grep -c "cron create" adapters/openclaw/SCHEDULING.md` ≥ 4.

### Step 3: skills/interaction-contract/SKILL.md
По структуре соседних скиллов. Назначение: Block C онбординга + смена ритма
в любой момент. Поведение: показать три ритма с честными цифрами объёма
(daily: ~10–20 мин/день первые 2 недели, потом ~5; weekly: 45–60 мин сессия на
старте; immediate: максимум дёргания); записать выбор в INTERACTION_CONTRACT.md;
установить кроны по SCHEDULING.md; ответить одной строкой-зеркалом. Правила:
это НЕ модель — без propose-change/ревью; но смена подтверждается явным ответом
владельца; high-risk полосы нет by design. What good looks like + 2 кейса
(смена ритма фразой «давай раз в неделю»; попытка третьего лица в группе сменить
ритм → отказ: настройки меняет владелец в личке).
**Verify**: файл существует; `grep -n "NOT.*model\|not part of the company model" skills/interaction-contract/SKILL.md` ≥ 1.

### Step 4: Сшивки + прогон
OPERATING_LOOP.md: «On each scheduled run» → «On each scheduled run (schedule
defined by the interaction contract, see adapters/openclaw/SCHEDULING.md)».
BOOTSTRAP.md: после онбординга — установить кроны выбранного профиля.
skills/README.md: добавить скилл.
**Verify**: `grep -rn "SCHEDULING.md" agent-os/ adapters/ | wc -l` ≥ 2;
тесты OK; евалы 0 failed.

## Test plan

Кода нет; grep-verify + полный прогон тестов/евалов. Поведенческие кейсы —
в SKILL.md.

## Done criteria

- [ ] 3 новых файла существуют, grep-verify проходят
- [ ] `python3 -m unittest discover -s tests -q` → OK; евалы 0 failed
- [ ] Рабочее дерево чистое; история — осмысленные шаги

## STOP conditions

- Eval, проверяющий состав templates/workspace (если есть), падает от нового
  шаблона — доложить.
- Обнаружен существующий механизм расписаний в репо, противоречащий SCHEDULING.md —
  доложить, не плодить второй контракт.

## Maintenance notes

- При live-деплое сверить cron-синтаксис с фактической версией OpenClaw.
- Команды /rhythm в TELEGRAM_COMMANDS — только если фразы окажется мало.
