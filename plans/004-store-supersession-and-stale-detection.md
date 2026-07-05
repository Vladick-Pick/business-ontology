# Plan 004: Починить два расхождения контракт/код — суперсессия в store и stale-детекция пакетов

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat e23d69b..HEAD -- runtime/operational_store.py runtime/reference_runtime.py tests/`
> Расхождение с «Current state» = STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (меняет write-path store; смягчение — красные тесты сначала)
- **Depends on**: none
- **Category**: bug (код нарушает собственный контракт)
- **Planned at**: commit `e23d69b`, 2026-07-02

## Why this matters

Два места, где реализация нарушает собственные контракты репозитория:

1. **Суперсессия перезаписывает историю.** Контракт (`references/canonical-model-store.md`,
   Failure modes) называет «superseded state is overwritten instead of linked»
   дефектом-блокером, но `record_accepted_item` делает UPSERT — прежняя версия
   физически исчезает из store. История выживает только в git-экспорте.
2. **stale-детекция — контракт без кода.** Каждый model-change package несёт
   `ontologyRevision` ровно затем, чтобы ревью ловило пакеты, скомпилированные против
   устаревшей модели (`references/model-change-package.md`); `agent-os/OPERATING_LOOP.md`
   называет это stop condition. Фактически `_package_summary` возвращает `"stale": False`
   захардкожено — пакет против устаревшей ревизии пройдёт ревью как свежий.

## Current state

- `runtime/operational_store.py:468` — `ON CONFLICT(item_id)` в `record_accepted_item`
  (UPSERT: DO UPDATE перетирает строку); аналогично `:742` (workflow), `:922` (binding),
  `:1006` (instance), `:1085` (relation).
- `runtime/operational_store.py:2018` — в `_package_summary`: `"stale": False,` —
  константа; `:1617` — `list_pending_model_change_packages` → `[_package_summary(row)…]`.
- `runtime/operational_store.py` — колонки `valid_from/valid_to` у items/definitions/
  workflows уже есть; колонок `supersedes/superseded_by/version_id` нет.
- `runtime/reference_runtime.py` — `_local_revision` (sha256 канонизированного экспорта)
  и `_store_revision`; ресурс `review/packages` отдаёт сводки пакетов.
- `apply_approved_model_change` в operational_store.py применяет approved-пакеты.
- Тестовый паттерн: `tests/test_operational_store.py` (существует — найди:
  `ls tests/ | grep store`).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты store | `python3 -m unittest tests.test_operational_store -q` | OK |
| Все тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |

## Scope

**In scope:**
- `runtime/operational_store.py` (record_accepted_item/workflow, _package_summary,
  apply_approved_model_change, миграция схемы SQLite)
- `runtime/reference_runtime.py` (передача текущей ревизии в сводки пакетов)
- `tests/test_operational_store.py` (+ новые тесты)

**Out of scope:**
- bindings/instances/relations UPSERT-ы (:922, :1006, :1085) — версионируем только
  items и workflows в этом плане; остальное — follow-up (см. Maintenance).
- Markdown-путь (staged/) — не трогать; git-история там уже работает.
- Схемы JSON в schemas/ — контракт уже требует этого поведения.

## Git workflow

- Ветка от main: `feature/store-supersession-stale`
- TDD: красный тест → фикс → зелёный. Коммит на шаг.

## Steps

### Step 1: Красные тесты суперсессии
В `tests/test_operational_store.py`: тест «две версии одного item_id обе queryable»:
записать item A (v1), записать item A с изменённым полем (v2) → `get_accepted_item(A)`
возвращает v2; новый метод `get_item_history(A)` возвращает обе, у v1 `valid_to` ≠ null
и `superseded_by` = version-id v2, у v2 `supersedes` = version-id v1. Аналогичный тест
для workflow.
**Verify**: `python3 -m unittest tests.test_operational_store -q` → 2 новых теста FAILED
(остальные OK).

### Step 2: Версионирование вместо UPSERT
Миграция схемы: добавить `version_id TEXT`, `supersedes TEXT`, `superseded_by TEXT`
в accepted_items/accepted_workflows (ALTER TABLE в _ensure_schema-механизме store —
найти как store создаёт таблицы и добавить туда же). `record_accepted_item`: если
item_id существует и текущая версия открыта (valid_to IS NULL) — закрыть её
(valid_to=now, superseded_by=new_version_id) и INSERT новой строки с
supersedes=old_version_id; НЕ UPDATE содержимого. `get_accepted_item` — только
текущая (valid_to IS NULL). Добавить `get_item_history(item_id)`.
Дочерние definitions/attributes/criteria: привязать к version_id (или скопировать
на новую версию — выбрать по фактической схеме; если дочерние таблицы ссылаются
только на item_id — скопировать строки на новую версию).
**Verify**: Step 1 тесты зелёные; `python3 -m unittest discover -s tests -q` → OK.

### Step 3: Красный тест stale
Тест: записать пакет с `ontologyRevision: "rev-A"`; вызвать листинг с текущей
ревизией "rev-B" → сводка несёт `stale: True`; `apply_approved_model_change` для
stale-пакета без `allow_stale=True` → исключение с внятным сообщением.
**Verify**: тест FAILED.

### Step 4: Реализация stale
`_package_summary(row, current_revision=None)`: `stale = bool(current_revision and
row["ontology_revision"] and row["ontology_revision"] != current_revision)`.
Прокинуть current_revision из вызывающих мест (`list_pending_model_change_packages`
и reference_runtime, где ревизия уже вычисляется как `_local_revision`/
`_store_revision`). В `apply_approved_model_change` — проверка + параметр
`allow_stale: bool = False`.
**Verify**: Step 3 тест зелёный; все тесты OK; `python3 scripts/run_evals.py
--fixture-only` → 0 failed (если кейс падает из-за нового поля stale в сводке —
это ожидаемое обновление фикстуры: доложить, не править фикстуры молча — STOP).

## Test plan

Новые тесты (Step 1, 3): суперсессия items, суперсессия workflows, история двух
версий, stale=True при несовпадении ревизий, stale=False при совпадении,
apply отказывает stale-пакету, apply с allow_stale=True проходит.
Паттерн — существующие тесты в tests/test_operational_store.py.

## Done criteria

- [ ] `python3 -m unittest discover -s tests -q` → OK, ≥7 новых тестов
- [ ] `grep -n "ON CONFLICT(item_id)" runtime/operational_store.py` → 0 вхождений
- [ ] `grep -n '"stale": False,' runtime/operational_store.py` → 0 вхождений
- [ ] `python3 scripts/run_evals.py --fixture-only` → 0 failed
- [ ] `plans/README.md` обновлён

## Решение по STOP-условию FK (advisor, 2026-07-02, раунд REVISE 1)

Исполнитель корректно остановился: дочерние таблицы (accepted_definitions/attributes/
criteria/examples, accepted_data_bindings, accepted_instances → item_id;
accepted_workflow_* → workflow_id) держат `FOREIGN KEY ... ON DELETE CASCADE`, а SQLite
требует UNIQUE-цель FK — несовместимо с многоверсионностью item_id.

**Принято: вариант (a)** — при пересборке таблиц accepted_items/accepted_workflows
(version_id как PRIMARY KEY, обычный неуникальный индекс по item_id/workflow_id)
FK-клаузы дочерних таблиц заменяются обычными индексами по тем же колонкам;
референциальная целостность обеспечивается приложением (children пишутся только
внутри record_accepted_item/workflow в одной транзакции) + интеграционный тест
«ни одного ребёнка без родителя». Обоснование: дети принадлежат месту (item_id),
а не версии; store append-only — DELETE для items в API нет, CASCADE мёртвый;
дублирование детей на версию (вариант b) раздуло бы store и противоречило
идемпотентности. Комментарий в схеме обязан объяснить, почему FK нет.
Миграция существующих БД: если PRAGMA table_info(accepted_items) не содержит
version_id — table-rebuild (create new → copy → drop → rename) в механизме
гарантии схемы. Заодно зафиксировать в отчёте: включает ли store
PRAGMA foreign_keys (для понимания, были ли FK вообще активны).

## STOP conditions

- Дочерние таблицы store связаны с items сложнее, чем по item_id (композитные ключи,
  каскады) — доложить фактическую схему перед Step 2.
- Существующий eval/фикстура зависит от UPSERT-семантики (перезапись как фича) —
  доложить конфликт контрактов.
- Изменение сигнатуры `_package_summary` ломает >3 вызывающих мест — доложить список.

## Maintenance notes

- Follow-up (сознательно отложено): версионирование bindings/instances/relations;
  ресурс `model/current?asOf=` (time-travel) поверх version_id.
- Ревьюеру: проверить, что `record_human_decision`/идемпотентность пакетов не
  задеты (терминальные статусы по-прежнему нельзя переписать).
