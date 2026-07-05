# Plan 002: Модель данных v2 — схемы, валидатор, миграция, эталонный бизнес

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. On any STOP condition — stop and report. When done, update
> `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat e23d69b..HEAD -- schemas/ scripts/links_validate.py references/ examples/`
> При изменениях сверить «Current state» с живым кодом; расхождение = STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (меняет центральный контракт; смягчение — алиасы и warning-режим)
- **Depends on**: none (но релиз 007 зависит от этого плана)
- **Category**: migration + tech-debt
- **Planned at**: commit `e23d69b`, 2026-07-02

## Why this matters

Текущая таксономия v1 (7 типов) прячет реальные типы в `attrs.subtype` без контрактной
силы: метрика не обязана нести формулу, роль — полномочия, owner — свободная строка.
Тип `process` — единственный без примера. Стресс-тест на живом источнике (MCP-дашборд
Привлечения) подтвердил v2 на ~85% и дал 5 точечных патчей. Спецификация v2 полностью
записана владельцем в файле `/Users/vladislavbogdan/Онтология тест/МОДЕЛЬ-ДАННЫХ-v2.md`
— этот план переносит её в репозиторий и имплементирует.

## Current state

- `schemas/card.schema.json:12-22` — закрытый enum 7 типов:
  `concept, module, production-system, interface, process, state, decision`.
- `scripts/links_validate.py:25` — `ALLOWED_LINKS = {` (9 отношений);
  `:115` — `ALLOWED_ATTRS = {` (attrs-контракт по типам живёт здесь, не в JSON-схеме).
- `references/templates.md` — шаблоны карточек v1; `references/structure.md` — слои.
- `examples/acquisition-ontology/` — эталонный модуль v1 (10 карточек, без process).
- Нормативный источник v2 (ЧИТАТЬ ПЕРВЫМ):
  `/Users/vladislavbogdan/Онтология тест/МОДЕЛЬ-ДАННЫХ-v2.md`. Ключевое:
  - 11 типов: `business` (пере­именование module; алиас module — одну версию),
    `production-system`, `role`, `artifact`, `tool`, `metric`, `state`, `process`,
    `interface`, `decision`, `term`;
  - 10 отношений: 9 прежних, `in-state` → `lifecycle` (алиас на переходную версию),
    `+influences` (рёберные attrs polarity/delay, evidence обязателен);
  - закрытые attrs-контракты на тип (метрика: formula/unit/direction/binding…;
    state: entity/entry/terminal/transitions/reason-codes; process: steps[…];
    interface: contract handoff|contract + qualities/slas/acceptance; decision:
    12 полей v1 + norm-kind/supersedes/valid-from…);
  - общие поля: aliases, evidence, volatility; owner → role-id|unknown;
  - правила V1–V9 (§4 спеки) и миграционная таблица (§6).
- Конвенция репо: «If you change the relation list, update ai-ready.md, the
  validator, and registry-spec.md together» — менять контракт можно только
  синхронно во всех трёх местах + CHANGELOG.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK (271 до, больше после) |
| Валидатор на примере | `python3 scripts/links_validate.py examples/acquisition-ontology` | errors: 0 |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |

## Scope

**In scope:**
- `docs/specs/2026-07-02-data-model-v2.md` (создать — копия нормативной спеки)
- `schemas/card.schema.json` (v2: типы, общие поля), `schemas/diagram*`-нет,
  `schemas/model-change-package.schema.json` (candidateCard типы)
- `scripts/links_validate.py` (ALLOWED_LINKS, ALLOWED_ATTRS, правила V1–V9)
- `scripts/migrate_taxonomy_v2.py` (создать)
- `references/templates.md`, `references/structure.md`, `references/ai-ready.md`,
  `references/registry-spec.md` (синхронное обновление)
- `examples/business-attraction-v2/` (создать эталонный бизнес v2)
- `staged/` — decision-карточка об изменении контракта (самодемонстрация протокола)
- `tests/test_links_validate*.py`, `tests/test_build_registry.py` (расширить)

**Out of scope:**
- `runtime/*` (компилятор/store — планы 004/006), `viewer/*` (план 001),
  `agent-os/*` поведенческие политики, `deployment/*`.
- Удаление v1-примера `examples/acquisition-ontology/` — оставить до конца
  переходной версии (валидатор принимает алиасы module/in-state).

## Git workflow

- Ветка от main: `feature/data-model-v2`
- Коммит на шаг; стиль: краткий императив как в `git log --oneline`.
- Не пушить и не открывать PR без команды оператора.

## Steps

### Step 1: Внести спеку и decision-карточку
Скопировать `/Users/vladislavbogdan/Онтология тест/МОДЕЛЬ-ДАННЫХ-v2.md` в
`docs/specs/2026-07-02-data-model-v2.md`. Создать в `staged/` decision-карточку
`d-data-model-v2` (status proposed, norm-kind decided, episode 2026-07-02,
scope: контракт карточек/отношений, blast-radius: schemas+validator+templates,
Considered alternatives: «оставить subtype», «открытый словарь отношений»).
**Verify**: `python3 scripts/links_validate.py . --staged` → 0 errors.

### Step 2: Схемы v2
`card.schema.json`: enum type → 11 значений + `module` (deprecated-алиас, оставить
в enum с комментарием в description); добавить optional `aliases: []`,
`evidence: []`, `volatility`. В `model-change-package.schema.json` обновить enum
типов candidateCard аналогично.
**Verify**: `python3 -m unittest tests.test_run_evals -q 2>/dev/null || python3 -m unittest discover -s tests -q` → OK.

### Step 3: Валидатор v2
В `links_validate.py`: ALLOWED_LINKS + `lifecycle` (и алиас `in-state` → warning
«deprecated, use lifecycle»), + `influences` (требует attrs polarity на ребре —
формат `influences: [{id, polarity, delay?}]` описать в ai-ready.md);
ALLOWED_ATTRS — закрытые контракты 11 типов из спеки §2; новые правила:
owner→role|unknown (warning-режим), взаимность artifact.lifecycle↔state.entity,
запрет owns при part-of той же пары, entry/terminal ⊆ states, reason-codes[].on ∈
terminal, steps[].role резолвится. Бизнес без produces — warning.
**Verify**: `python3 scripts/links_validate.py examples/acquisition-ontology` →
0 errors (v1-алиасы работают), warnings допустимы.

### Step 4: Миграционный скрипт
`scripts/migrate_taxonomy_v2.py <ontology-root> [--dry-run]`: переписывает по
таблице §6 спеки (subtype product/service→artifact и т.д.; module→business;
attrs.parent-module → рёбра part-of; in-state→lifecycle). Id НЕ меняет. Спорное
(fact/other) — выводит списком «требует ревью», не трогает.
**Verify**: `python3 scripts/migrate_taxonomy_v2.py examples/acquisition-ontology --dry-run`
→ печатает план миграции, exit 0.

### Step 5: Эталонный бизнес v2
Создать `examples/business-attraction-v2/` по образцу структуры
`examples/acquisition-ontology/`, но на v2: biz-attraction, ps-attraction,
r-ki, a-deal, t-bitrix24, m-sla1 (полный metric-контракт с binding),
st-deal (entry/terminal/transitions с sla + reason-codes),
**p-handle-delivery (пример process с steps — впервые!)**,
if-lidgen-attraction (contract: qualities/slas/acceptance),
d-autopurchase (norm-kind regulated, irreversible true), tm-delivery-quality.
Одна influences-пара для петли. Данные брать из docs/specs спеки (§2 примеры).
**Verify**: `python3 scripts/links_validate.py examples/business-attraction-v2` → 0 errors;
`python3 scripts/build_registry.py examples/business-attraction-v2 --out /tmp/reg-v2`
→ nodes/edges созданы.

### Step 6: Синхронизация references + тесты
Обновить templates.md (шаблоны 11 типов), ai-ready.md (таблица 10 отношений),
registry-spec.md (derived-рёбра: инверсии, stage/step-edges, influences-циклы —
как контракт, реализация компилятора не в этом плане). Добавить тесты:
валидатор ловит чужой attrs-ключ; migrate --dry-run идемпотентен; example v2
компилируется.
**Verify**: `python3 -m unittest discover -s tests -q` → OK, счётчик тестов вырос.

## Test plan

Новые тесты в `tests/test_links_validate_v2.py` (создать, по образцу существующего
теста валидатора): (1) v2-типы принимаются; (2) module-алиас даёт warning, не error;
(3) metric без formula → error «attrs contract»; (4) owns+part-of одной пары → error;
(5) reason-codes[].on вне terminal → error; (6) influences без polarity → error.

## Done criteria

- [ ] `python3 scripts/links_validate.py examples/business-attraction-v2` → 0 errors
- [ ] `python3 scripts/links_validate.py examples/acquisition-ontology` → 0 errors (обратная совместимость)
- [ ] `python3 -m unittest discover -s tests -q` → OK
- [ ] `python3 scripts/run_evals.py --fixture-only` → 0 failed
- [ ] В examples/business-attraction-v2 есть process-карточка со steps
- [ ] docs/specs/2026-07-02-data-model-v2.md существует; staged/ содержит d-data-model-v2
- [ ] `plans/README.md` обновлён

## STOP conditions

- ALLOWED_ATTRS в links_validate.py структурно не таблица-словарь (рефакторинг
  сначала — доложить).
- Обратная совместимость ломается: v1-пример перестал проходить и починка требует
  менять v1-карточки (алиасный слой должен покрывать — если нет, доложить).
- Евалы падают из-за enum в схемах фикстур — доложить список, не править фикстуры
  молча.

## Maintenance notes

- Через одну версию: удалить алиасы module/in-state + мигрировать v1-пример.
- Компилятор influences-циклов (derived loops) и impact-обход — отдельные планы
  (deferred, см. README).
- Ревьюеру: проверить, что 12 кинетических attrs decision НЕ переименованы
  (совместимость с model-change-package схемой).
