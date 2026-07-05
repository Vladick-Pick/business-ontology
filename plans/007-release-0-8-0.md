# Plan 007: Релиз 0.8.0 — «Data model v2, position hardening, honest history»

> **Executor instructions**: Выполнять ТОЛЬКО после того, как планы 001–004 имеют
> статус DONE в plans/README.md (005/006 — если успели, включить в notes). On STOP —
> stop and report.
>
> **Drift check (run first)**: подтвердить статусы 001–004 в plans/README.md = DONE.

## Status

- **Priority**: P1 (закрывающий)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: 001, 002, 003, 004 (DONE); 005, 006 опционально
- **Category**: docs / release
- **Planned at**: commit `e23d69b`, 2026-07-02

## Why this matters

Релиз фиксирует итог разработки как проверяемую версию: новая модель данных
(v2-контракт), запертая позиция агента, честная история в store и рабочий вьюер.
Без релиза изменения размазаны по веткам и их нельзя назвать состоянием технологии.

## Current state

- `CHANGELOG.md` — последняя запись `0.7.0` на main (после мержа PR #8; на ветке
  feature/model-viewer виден 0.6.0 — брать main как базу).
- Процесс релиза описан в `docs/release-process.md` (прочитать перед Step 1).
- `agent-package.yaml` — метаданные пакета (проверить, есть ли поле версии:
  `grep -n version agent-package.yaml`).
- Открытый PR #9 (feature/model-viewer) должен быть вмержен в составе релиза
  (после плана 001) — мерж выполняет ЧЕЛОВЕК (правило репо: агент не мержит).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Валидатор примеров | `python3 scripts/links_validate.py examples/business-attraction-v2` | 0 errors |

## Scope

**In scope:** `CHANGELOG.md`, `agent-package.yaml` (версия, если поле есть),
`docs/release-process.md`-чеклист (выполнить, не менять).
**Out of scope:** любые правки кода/схем (они в планах 001–006); git merge/push —
только человек.

## Git workflow

- Ветка от main (после мержа веток планов): `release/0.8.0`.
- Один коммит «Release 0.8.0: data model v2, position hardening, honest history».
- PR открывает оператор; агент готовит текст.

## Steps

### Step 1: Черновик release notes в CHANGELOG.md

Секция `## 0.8.0 - Data model v2, position hardening, honest history` с блоками:

**Data model v2 (proposal + implementation):**
- 11 card types (business — renamed from module, production-system, role, artifact,
  tool, metric, state, process, interface, decision, term) with closed per-type
  attrs contracts; spec in docs/specs/2026-07-02-data-model-v2.md.
- 10 relations: `in-state` → `lifecycle` (alias kept for one version), new signed
  `influences` (polarity/delay, evidence-gated).
- Interface contract grades: `handoff` vs `contract` (qualities, SLAs with breach
  effects, acceptance incl. settlement).
- stages as PS-attr (state × processes × roles), reason-codes on states,
  metric binding (structure in model, values stay live).
- Migration script `scripts/migrate_taxonomy_v2.py`; reference business example
  `examples/business-attraction-v2/` (first `process` card with steps).

**Position hardening:**
- Operator-mode grant protocol (trace event `operator-mode-grant`; source text can
  never grant the mode) + trace check `trace_operator_grant_before_direct_write`.
- 5 position evals: pressure-accept escalation, consultant bait, mode-flip injection,
  trivial-source no-op, long-session discipline.
- Position recovery section in the skill; re-anchor step in the daily loop.

**Honest history & review:**
- Store supersession: versions instead of UPSERT (`supersedes`/`superseded_by`,
  `get_item_history`); superseded stays queryable — closes the contract blocker.
- Stale detection: packages compiled against an outdated `ontologyRevision` are
  flagged and refused by apply (override flag available).

**Viewer v2:**
- Whiteboard renderer (containers, decision diamonds, hexagons, sticky notes),
  funnel dashboard with live overlay (readings, not model), generated tables;
  ghost nodes for dangling links; card statuses visible on diagrams; dead Mermaid
  path removed.

(Если 005/006 DONE — добавить блоки First session playbook и Extraction golden
benchmark по их done-критериям.)

**Verify**: `grep -n "0.8.0" CHANGELOG.md` → секция сверху файла.

### Step 2: Чек-лист release-process
Выполнить шаги `docs/release-process.md` (read-only проверки: тесты, евалы,
валидатор, links).版ерсию в agent-package.yaml поднять, если поле есть.
**Verify**: все три команды из «Commands» зелёные.

### Step 3: Передать оператору
Сообщить оператору: ветка release/0.8.0 готова; список PR к мержу (PR #9 + ветки
планов 002–004[, 005, 006]); мерж и тег — за человеком.
**Verify**: сообщение оператору содержит полный список веток и статусы.

## Done criteria

- [ ] CHANGELOG.md содержит 0.8.0 с блоками по фактически вмерженным планам
- [ ] Тесты, евалы, валидатор зелёные на release-ветке
- [ ] plans/README.md: строка 007 → DONE, остальные статусы актуальны

## STOP conditions

- Любой из планов 001–004 не DONE — остановиться, доложить.
- docs/release-process.md требует шаг, недоступный агенту (публикация, тег) —
  явно передать его человеку, не имитировать выполнение.

## Maintenance notes

- Следующий релиз-кандидат (0.9.0): планы из deferred-списка README —
  graph impact API, time-travel, независимый грейдер экстракции, ревью-пропускная
  способность (матрица автономии), archify-экспортёр.
