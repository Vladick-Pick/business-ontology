# Plan 001: Закоммитить и укрепить вьюер v2 (whiteboard/funnel/таблицы) в PR #9

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat e23d69b..HEAD -- viewer/`
> Если viewer/ менялся после написания плана — сверь секцию «Current state»
> с живым кодом; при расхождении — STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt + dx
- **Planned at**: commit `e23d69b`, 2026-07-02

## Why this matters

В рабочем дереве ветки `feature/model-viewer` лежит НЕзакоммиченная вторая версия
вьюера: whiteboard-рендер (Miro-стиль: контейнеры, ромбы, шестиугольники, стикеры),
funnel-дашборд с live-оверлеем и генерируемые таблицы. Она протестирована владельцем
локально, но не входит в PR #9. Кроме того, в ней два известных дефекта: (1) висячая
ссылка в edges роняет всю «Карту модели» (dagre создаёт узел без label →
`dgNode(undefined)` → TypeError); (2) ~90 строк мёртвого Mermaid-кода + загрузка
mermaid.min.js (~2.8 МБ) с CDN, хотя Mermaid-функции больше нигде не вызываются.

## Current state

- `viewer/index.html` — однофайловый vanilla-JS вьюер. В git-дереве — версия с Mermaid
  (коммит e23d69b); в рабочем дереве — расширенная (dagre + wbSVG/wbNode/wbOrtho,
  funnelHTML, renderTable, DPEND-очередь). `git status --short` показывает
  `M viewer/index.html`, `M viewer/README.md`, `?? viewer/sample-clubfirst.json`,
  `?? viewer/archify-lead-lifecycle.html`.
- Мёртвый код: функции `mermaidBlock`, `modelMapCode`, `nodeSchemaCode`,
  `stateDiagramCode`, `processFlowCode` объявлены, но не вызываются
  (проверь: `grep -n "mermaidBlock(" viewer/index.html` — только определение).
- Крах карты: в `dgSVG` вызывается `g.nodes().forEach(id => dgNode(g.node(id)))`;
  для edge с несуществующим target dagre авто-создаёт узел без данных →
  `dgNode(undefined)` бросает TypeError, вся схема заменяется на «Схема не построилась».
- `viewer/archify-lead-lifecycle.html` — разовый экспорт-эксперимент, НЕ коммитить.
- Конвенции: вьюер зависимостей не имеет (кроме dagre с CDN), CSS-переменные
  свои (`--panel`, `--ink`, `--muted`, `--warn-bg`, `--bg`) — НЕ использовать
  токены других систем.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | `OK`, 271+ tests |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 25 passed, 0 failed |
| Сервер для ручной проверки | `python3 -m http.server 8787 --directory viewer` | открывается http://localhost:8787/ |

## Scope

**In scope:**
- `viewer/index.html`, `viewer/README.md`, `viewer/sample-clubfirst.json` (добавить в git)
- `.gitignore` (добавить `viewer/archify-*.html`)

**Out of scope:**
- `scripts/build_viewer_bundle.py` (генератор не трогаем в этом плане)
- `viewer/archify-lead-lifecycle.html` — НЕ коммитить, это scratch-экспорт
- Переход на elkjs — отложен (см. plans/README.md, deferred)

## Git workflow

- Ветка: текущая `feature/model-viewer` (PR #9 уже открыт — коммиты попадут в него)
- Стиль сообщений: короткий императив, как `git log --oneline -5`
  (пример: «Add read-only model viewer for verifying the ontology»)
- Не пушить без указания оператора.

## Steps

### Step 1: Зафиксировать рабочее дерево как есть

`git add viewer/index.html viewer/README.md viewer/sample-clubfirst.json` и коммит
«Add whiteboard renderer, funnel dashboard, and generated tables to viewer».
Добавить `viewer/archify-*.html` в `.gitignore` тем же коммитом.

**Verify**: `git status --short` → пусто (кроме untracked plans/); открыть
http://localhost:8787/#card/lead-lifecycle → воронка + доска рендерятся.

### Step 2: Ghost-узлы вместо краха на висячих ссылках

В `viewer/index.html`: в местах, где строится dagre-граф из edges (функция modelSpec
или аналог, и в `dgSVG`), перед добавлением ребра проверять существование целевой
карточки; для отсутствующей цели создавать ghost-узел: `{id, label: id, ghost: true}`,
рендерить серым пунктиром с подписью «нет карточки». В `dgNode`/`wbNode` — guard:
`if (!node) return` с console.warn.

**Verify**: временно добавить в sample-clubfirst.json ребро на несуществующий id,
открыть `#map` → карта рендерится, ghost-узел виден, консоль без TypeError; убрать
тестовое ребро.

### Step 3: Удалить мёртвый Mermaid-путь

Удалить функции `mermaidBlock`, `modelMapCode`, `nodeSchemaCode`, `stateDiagramCode`,
`processFlowCode`, `renderMermaidAll`, переменную PENDING (если использовалась только
Mermaid), и `<script>`-тег загрузки mermaid.min.js. Обновить `viewer/README.md`:
секцию «Diagrams (Mermaid)» заменить описанием whiteboard-рендера.

**Verify**: `grep -ci mermaid viewer/index.html` → 0; все маршруты
(#overview, #map, #card/lidgen, #card/proc-hot-pies, #card/lead-lifecycle) рендерятся,
консоль чистая.

### Step 4: Статусы карточек видимы на схемах

В `wbNode`/`dgNode`: если у карточки status ≠ accepted — рамка `stroke-dasharray:4 3`
(candidate), жёлтый ореол (hypothesis), красная рамка (conflict). Добавить строку-легенду
под SVG из фактически использованных статусов/фигур.

**Verify**: в sample-clubfirst.json карточка со status candidate отображается
пунктиром на #map; легенда присутствует.

## Test plan

Вьюер — статический HTML без тест-раннера; проверка ручная по маршрутам (Step 1-4
verify) + `python3 -m unittest` (не должен сломаться — вьюер не входит в тесты,
но build_viewer_bundle тестируется).

## Done criteria

- [ ] `git log --oneline -3` содержит коммиты Steps 1 и 3-4
- [ ] `grep -ci mermaid viewer/index.html` → 0
- [ ] Все 5 маршрутов открываются без ошибок консоли
- [ ] `viewer/archify-lead-lifecycle.html` отсутствует в `git status`
- [ ] `python3 -m unittest discover -s tests -q` → OK
- [ ] Строка статуса в `plans/README.md` обновлена

## STOP conditions

- Рабочее дерево НЕ содержит модификаций viewer/index.html (значит, кто-то уже
  закоммитил или откатил — сверься с оператором).
- После Step 3 какой-либо маршрут перестал рендериться и починка не удалась
  с двух попыток.

## Maintenance notes

- Следующий шаг эволюции — elkjs вместо dagre (ортогональная маршрутизация без
  пересечений) и кликабельность узлов (`<a href="#card/id">`); отложено сознательно.
- Ревьюеру PR #9: проверить, что удаление Mermaid не упомянуто в BOOTSTRAP.md шаге 7
  (там ссылка на вьюер, не на Mermaid — менять не надо).
