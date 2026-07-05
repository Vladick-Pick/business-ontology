# Plan 006 (v2, переписан 2026-07-05): АГЕНТНЫЙ бенчмарк экстракции — агент извлекает, скрипт только гоняет и считает

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Commit in worktree. SKIP updating plans/README.md.
>
> **Drift check (run first)**: `ls evals/golden scripts/run_extraction_benchmark.py 2>/dev/null`
> → оба отсутствуют; `grep -n "not a production" runtime/model_compiler.py | head -1`
> → есть (заглушка честно себя называет). Иначе STOP.

## Status

- **Priority**: P1 (обязателен до живого экстрактора) | **Effort**: L | **Risk**: LOW-MED
- **Depends on**: none | **Category**: tests + agent-harness
- **Planned at**: commit `c53bb14`, 2026-07-05
- **Заменяет**: v1 этого плана. Жёсткая поправка владельца: «экстракцией должен
  заниматься САМ АГЕНТ, а не скрипт». Скрипт в v1 подменял агента — неверная
  архитектура. Правильная граница (из работающего прецедента
  `/Users/vladislavbogdan/Documents/ИИ Богдан/openclaw-migration/server-current/workspace/skills/telegram-daily-ingest/SKILL.md:16`):
  **детерминированный код только собирает/гоняет/считает; смысл извлекает агент
  по скиллу.** «Do not outsource semantic interpretation to regex/script output».

## Why this matters

Экстракция — непостроенное звено технологии: события-источники должен превращать
в model-change-пакеты LLM-агент по скиллу `extract-from-input`, но его качество
никто не измеряет. Референс-заглушка `runtime/model_compiler.py` галлюцинирует
(выдаёт `affectedIds: ["unknown"]` + выдуманный candidateCard, ни разу не эмитит
needs-info) — и остаётся ЛИШЬ контрактной обвязкой для тестов водопровода, НЕ
прототипом экстрактора. Нужен бенчмарк, где **прогоняется агент**, а
детерминированный код лишь раскладывает кейсы и считает precision/recall.

## Current state

- `skills/extract-from-input/SKILL.md` — скилл агентной экстракции (прочитай
  целиком — бенчмарк меряет ЕГО работу; там уже есть запрет over-mining).
- `runtime/model_compiler.py:4` — «not a production/LLM compiler»; `:296` —
  handoff-ветка с `affectedIds: ["unknown"]` + candidateCard;
  `grep -c "needs-info" runtime/model_compiler.py` → 0. НЕ ТРОГАТЬ его экстракцию
  в этом плане (он — контрактная обвязка).
- `schemas/model-change-package.schema.json` — `proposedAction` содержит `needs-info`.
- Фикстуры-сырьё: `evals/fixtures/source-events/*.synthetic.json`,
  `evals/fixtures/model-change-packages/`.
- `scripts/run_evals.py` — детерминированный раннер (не вызывает LLM) — образец
  стиля для нового раннера.

## Архитектура бенчмарка (нормативно)

```
evals/golden/<case>/source-event.json + accepted-context/ + expected-changes.json
        │
        ▼
АГЕНТ по skills/extract-from-input  ──►  packages-out/<case>/mcpkg-*.json
(вызывается вне раннера: claude/codex/     (обычный model-change package)
 резидент — как угодно; раннер его            │
 НЕ содержит и НЕ подменяет)                  ▼
scripts/run_extraction_benchmark.py --golden evals/golden --packages packages-out
        = детерминированный СКОРЕР: валидность пакета по схеме, матчинг changes
        по (kind + affectedIds), precision/recall/F1 per kind, проверки
        «needs-info вместо галлюцинации», «нет candidateCard без evidence»,
        «evidence.excerpt дословно из события». Exit 1 ниже порога.
```

Заглушка может гоняться тем же скорером (`--packages` от её прогона) — как
baseline, который агент обязан побить; но она не часть бенчмарка.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Скорер | `python3 scripts/run_extraction_benchmark.py --golden evals/golden --packages <dir>` | таблица P/R/F1, exit-код по порогу |

## Scope

**In scope:** `evals/golden/` (6–8 кейсов), `scripts/run_extraction_benchmark.py`
(создать), `tests/test_run_extraction_benchmark.py` (создать),
`skills/extract-from-input/SKILL.md` (добавить правила: needs-info деградация;
запрет `prepare-staged-proposal` + `affectedIds:["unknown"]`; «оцениваешься
бенчмарком — evals/golden/README.md»), `evals/golden/README.md` (как прогнать
агента по кейсам: пример команды для claude/codex, формат packages-out),
`scripts/run_evals.py` (только линт: запрет сочетания prepare-staged-proposal
+ affectedIds unknown в ЛЮБЫХ пакетах).

**Out of scope:** правка экстракции в `runtime/model_compiler.py` (обвязка,
не экстрактор); вызов LLM из раннера (раннер детерминированный — НИКОГДА);
CI-интеграция агентных прогонов.

## Git workflow

- Ветка от main: `feature/agent-extraction-benchmark`; TDD для скорера.

## Steps

### Step 1: Формат golden-кейса + 6 кейсов
`evals/golden/<case-id>/`: `source-event.json` (валиден по схеме),
`accepted-context/` (мини-срез принятых карточек, если кейсу нужен контекст
сравнения), `expected-changes.json`:
`[{kind, affectedIds, proposedAction?, matchKey: "kind+affectedIds", optional: false}]`.
6 кейсов из фикстур-сырья: drift, conflict, new-object, dashboard-metric-concern,
no-op, handoff-underspecified (expected: ровно один change с
`proposedAction: "needs-info"`, БЕЗ candidateCard).
**Verify**: `ls evals/golden | wc -l` → ≥6; каждый source-event проходит
существующую схему.

### Step 2: Скорер (TDD)
`scripts/run_extraction_benchmark.py` (stdlib): вход `--golden`, `--packages`
(каталог пакетов агента, по подкаталогу или префиксу на кейс — задокументируй
соглашение в --help), `--min-f1 0.8`. На кейс: пакет валиден по
model-change-package.schema.json (переиспользуй механизм run_evals, не копируй);
changes матчатся к expected по matchKey; считаются per-kind и общие P/R/F1;
доп-проверки: (а) для underspecified-кейса — needs-info присутствует,
candidateCard отсутствует; (б) `evidence[].excerpt` каждого change встречается
в source-event (verbatim, анти-галлюцинация); (в) `prepare-staged-proposal` +
`affectedIds:["unknown"]` = автопровал кейса. Выход: таблица + `scorecard.json`;
exit 1 если total F1 < порога.
**Verify**: `python3 -m unittest tests.test_run_extraction_benchmark -q` → OK
(тесты: идеальные пакеты → F1=1.0; пропуск → recall падает; лишний change →
precision падает; excerpt не из события → кейс fail; галлюцинация unknown → fail).

### Step 3: Baseline заглушки — доказательство, что бенчмарк ловит
Прогнать `runtime/model_compiler.py` по golden-кейсам (мини-скрипт или прямой
вызов compile в тесте), сложить пакеты в `/tmp/baseline-packages`, прогнать скорер.
ОЖИДАЕМО низкий скор (галлюцинация на underspecified-кейсе = fail) — это
доказательство чувствительности бенчмарка, НЕ повод чинить заглушку.
Зафиксировать фактический baseline-скор в evals/golden/README.md.
**Verify**: скорер на baseline → exit 1; в README записана строка
«reference-stub baseline: F1=<факт>».

### Step 4: Скилл + линт + README
`skills/extract-from-input/SKILL.md`: правила needs-info деградации (не хватает
supplier/customer/subject в evidence — эмить needs-info с перечнем недостающего,
НЕ выдумывай candidateCard), запрет unknown-галлюцинации, ссылка на бенчмарк как
приёмку. `evals/golden/README.md`: как исполнить агентный прогон (пример:
на кейс — скормить агенту skills/extract-from-input + source-event + context,
собрать пакеты в packages-out; команды для claude -p / codex exec как примеры,
без зависимости от конкретного CLI). `scripts/run_evals.py`: линт
prepare-staged-proposal+unknown для всех пакетов-фикстур.
**Verify**: `python3 scripts/run_evals.py --fixture-only` → 0 failed
(если существующая фикстура ловится линтом — STOP, доложить список).

## Test plan
Тесты скорера (Step 2, 5+), без сети и без LLM. Паттерн — существующие тесты
scripts/.

## Done criteria

- [ ] 6+ golden-кейсов; скорер работает; baseline заглушки записан и провален
- [ ] Раннер НЕ вызывает LLM (grep: нет anthropic/openai/subprocess-вызовов агентов)
- [ ] skills/extract-from-input содержит needs-info правила и ссылку на бенчмарк
- [ ] Тесты OK (счётчик вырос ≥5), евалы 0 failed, ≥4 коммита

## STOP conditions

- Механизм валидации схем в run_evals нельзя переиспользовать без копипасты
  >30 строк — доложить.
- Существующие фикстуры содержат запрещённое сочетание — доложить, не править.

## Maintenance notes

- Приёмка замены заглушки на живого агента-экстрактора = агентный прогон этого
  бенчмарка с F1 ≥ порога (фиксируется в отчёте прогона).
- Следующий слой: регрессии из отклонённых пакетов, независимый грейдер
  evidenceGrade, калибровка confidence (deferred, README).
