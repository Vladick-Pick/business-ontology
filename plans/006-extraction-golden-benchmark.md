# Plan 006: Golden-бенчмарк экстракции — скоринг precision/recall и деградация к needs-info

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat e23d69b..HEAD -- runtime/model_compiler.py evals/ scripts/run_evals.py`
> Расхождение с «Current state» = STOP.

## Status

- **Priority**: P2 (обязателен ДО замены детерминированного компилятора на LLM-агента)
- **Effort**: L
- **Risk**: LOW-MED (новые скрипты + правка компилятора; поведение меняется только
  для недоопределённых событий)
- **Depends on**: none (совместим с 002; enum типов брать из текущих схем)
- **Category**: tests + correctness
- **Planned at**: commit `e23d69b`, 2026-07-02

## Why this matters

Сейчас евалы проверяют ФОРМУ пакетов (не мутирует accepted, поля валидны), но не
КАЧЕСТВО экстракции: находит ли компилятор все изменения из события и не выдумывает ли
лишних. Референс-компилятор демонстрирует ровно тот паттерн галлюцинации, который
LLM-агент повторит в проде: при слабом сигнале выдаёт захардкоженный candidateCard
с `affectedIds: ["unknown"]` и ни разу не эмитит `needs-info`. Без golden-набора
и метрик замену заглушки на агента будет нечем принять или отклонить.

## Current state

- `runtime/model_compiler.py:307-311` — ветка handoff-изменения:
  `"affectedIds": ["unknown"],` и следом candidateCard `"id": "if-acquisition-sales-handoff"`
  с выдуманными participants. `grep -c "needs-info" runtime/model_compiler.py` → 0.
- `schemas/model-change-package.schema.json` — proposedAction содержит `needs-info`
  (проверь: `grep -n '"needs-info"' schemas/model-change-package.schema.json`).
- Фикстуры-источники: `evals/fixtures/source-events/*.synthetic.json`;
  фикстуры-пакеты: `evals/fixtures/model-change-packages/` (используй как сырьё
  для golden-кейсов).
- Компиляция события в пакет: `scripts/compile_model_change.py` (проверь наличие:
  `ls scripts/ | grep compile`) либо прямой вызов `runtime/model_compiler.compile_model_change`.
- Раннер: `scripts/run_evals.py` — check-types реализованы функциями; новые
  check-types добавляются рядом с существующими (найди `check_model_change_package`).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Новый скоринг | `python3 scripts/score_extraction.py evals/golden` | таблица P/R/F1, exit 0 |

## Scope

**In scope:**
- `evals/golden/` (создать: 6–8 кейсов) — формат:
  `<case-id>/{source-event.json, accepted-context.json?, expected-changes.json}`
- `scripts/score_extraction.py` (создать)
- `runtime/model_compiler.py` (функция `_needs_info_change`, правка handoff-ветки)
- `scripts/run_evals.py` (линт: запрет `prepare-staged-proposal` + `affectedIds: ["unknown"]`;
  check-type `extraction_scorecard`)
- `evals/cases/underspecified-event-degrades-to-needs-info.json` (создать)
- `tests/test_model_compiler.py` (расширить)

**Out of scope:**
- Двухпроходная экстракция/адъюдикатор — deferred (README)
- Независимый грейдер evidenceGrade — deferred
- Калибровка confidence — deferred

## Git workflow

- Ветка от main: `feature/extraction-golden`; TDD, коммит на шаг.

## Steps

### Step 1: Формат golden-кейса + 6 кейсов
`evals/golden/<case-id>/`: `source-event.json` (валидный по source-event.schema.json),
опц. `accepted-context.json`, `expected-changes.json` — список
`{kind, affectedIds, matchKey: "kind+affectedIds", optional: false}`. Засеять 6 кейсов
из существующих фикстур (drift, conflict, new-object, dashboard-metric-concern,
no-op, handoff-underspecified). Для handoff-underspecified expected =
`[{kind: "new-object", proposedAction: "needs-info"}]`.
**Verify**: `ls evals/golden | wc -l` → 6; каждый source-event проходит существующую
схему (прогнать через run_evals check или jsonschema, если доступен).

### Step 2: score_extraction.py
Прогоняет компилятор по каждому golden-кейсу, матчит полученные changes с
expected по matchKey, считает per-kind и общие precision/recall/F1, печатает
таблицу + пишет `scorecard.json`. Exit 1, если total F1 < порога (по умолчанию 0.8,
флаг `--min-f1`).
**Verify**: `python3 scripts/score_extraction.py evals/golden` → таблица печатается;
ожидаемо низкий recall/precision на underspecified-кейсе (заглушка пока галлюцинирует)
— на этом шаге допустим exit 1 с флагом `--min-f1 0`.

### Step 3: needs-info деградация в компиляторе
В `runtime/model_compiler.py`: функция `_needs_info_change(event, missing: list[str])`
→ change с `proposedAction: "needs-info"`, evidence из события, summary с перечнем
недостающего. Правка handoff-ветки (строки ~296–328): если в evidence события не
именуются supplier/customer/subject — эмитить needs-info вместо candidateCard;
`affectedIds: ["unknown"]` больше не сочетается с `prepare-staged-proposal`.
**Verify**: `grep -c "needs-info" runtime/model_compiler.py` ≥ 2;
`python3 -m unittest tests.test_model_compiler -q` → OK (после Step 5 тестов).

### Step 4: Линт в раннере
В `scripts/run_evals.py` (внутри проверки пакетов): сочетание
`proposedAction == "prepare-staged-proposal"` и `affectedIds == ["unknown"]` → fail
с сообщением «underspecified change must degrade to needs-info».
**Verify**: `python3 scripts/run_evals.py --fixture-only` → 0 failed (если фикстура
содержит запрещённое сочетание — STOP, доложить: фикстура фиксировала старое
поведение).

### Step 5: Eval-кейс + тесты
`evals/cases/underspecified-event-degrades-to-needs-info.json` (по образцу соседних
кейсов): фикстурное событие с handoff без участников; проверки: пакет содержит
needs-info change, `not_contains: "candidateCard"`. Юнит-тесты в
tests/test_model_compiler.py: (а) underspecified → needs-info; (б) полное событие →
candidateCard как раньше; (в) needs-info несёт evidence.
**Verify**: `python3 scripts/run_evals.py --fixture-only` → 26+ passed, 0 failed;
`python3 -m unittest discover -s tests -q` → OK.

### Step 6: Scorecard-порог
Включить `extraction_scorecard` check-type в run_evals (вызывает score_extraction
c `--min-f1 0.8`); теперь заглушка обязана проходить порог на golden (после Step 3
underspecified-кейс даёт needs-info и матчится).
**Verify**: `python3 scripts/run_evals.py --fixture-only` → 0 failed, в выводе
строка scorecard.

## Test plan

См. Step 5. Дополнительно: тест score_extraction на синтетике (2 kase, 1 промах →
precision/recall считаются правильно) в `tests/test_score_extraction.py`.

## Done criteria

- [ ] `python3 scripts/score_extraction.py evals/golden --min-f1 0.8` → exit 0
- [ ] `grep -n 'affectedIds": \["unknown"\]' runtime/model_compiler.py` → 0 вхождений
  в сочетании с prepare-staged-proposal (проверить контекст руками)
- [ ] Все тесты и евалы зелёные
- [ ] `plans/README.md` обновлён

## STOP conditions

- Структура run_evals не позволяет добавить check-type без рефакторинга (>50 строк) —
  доложить с предложением.
- Существующие фикстурные пакеты содержат `affectedIds: ["unknown"]` c
  prepare-staged-proposal — доложить список (их правка = отдельное решение).
- Компилятор не имеет единой точки эмиссии changes (правка расползается) — доложить.

## Maintenance notes

- Прод-агент (LLM-экстрактор) обязан прогоняться этим же score_extraction — порог
  приёмки замены заглушки.
- Следующие уровни (deferred): регрессии из отклонённых пакетов, независимый грейдер
  evidenceGrade, drift-detection бенчмарк, калибровка confidence.
