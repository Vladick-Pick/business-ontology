# Модель данных v2 «модели компании» — нормативная спецификация

> Доведение [ПРЕДЛОЖЕНИЕ-таксономия-v2.md](ПРЕДЛОЖЕНИЕ-таксономия-v2.md) до имплементируемого
> контракта: по этому документу пишутся `schemas/*.json`, валидатор, шаблоны карточек и мишень
> экстракции для агента. Примеры — из реальности Clubfirst (Битрикс, корзина, горячие пирожки).
> Критерий приёмки: модель кормит 6 systems-thinking-скиллов без выдумывания структуры.

---

## 0. Мета-контракт: общий хребет любой карточки

```yaml
id: <opaque-kebab-case>          # обязателен, стабилен, НЕ производен от имён (`--` запрещён)
type: <один из 11>               # обязателен, закрытый список
status: <см. §0.3>               # обязателен
source: <source-id | unknown>    # обязателен, резолвится в 02-source-map.md
owner: <role-id | unknown>       # обязателен, резолвится в role-карточку (v2!)
last-reviewed: <date | unknown>  # обязателен
next-audit: <date | unknown>     # обязателен (дефолт от volatility, §0.4)
aliases: []                      # опц.: старые/жаргонные имена — для матчинга при майнинге
evidence: []                     # опц.: srcevt-*/prop-*, обосновавшие текущее принятие
volatility: high|medium|low      # опц.: скорость устаревания → каденция аудита
links: {}                        # только отношения из закрытого списка §3
attrs: {}                        # только типо-специфичные поля из контракта типа §2
```

**0.1. Id-дисциплина.** Непрозрачный, стабильный, lowercase-kebab. Рекомендованные префиксы
(машиночитаемость для агентов; обязателен только `if-` — унаследовано от v1):

| Тип | Префикс | Пример |
|---|---|---|
| business («бизнес») | `biz-` | `biz-lidgen` |
| production-system | `ps-` | `ps-bitrix` |
| role | `r-` | `r-qualifier` |
| artifact | `a-` | `a-qualified-lead` |
| tool | `t-` | `t-bitrix24` |
| metric | `m-` | `m-conv-meeting` |
| state | `st-` | `st-lead-lifecycle` |
| process | `p-` | `p-hot-pies` |
| interface | `if-` (обязателен) | `if-lidgen-sales` |
| decision | `d-` | `d-korzina-reasons` |
| term | `tm-` | `tm-hot-lead` |

**0.2. Правило трёх мест.** Связи — только в `links` (рёбра графа). Типо-специфичные не-связи —
только в `attrs` (контракт закрыт по типу, чужие ключи — ошибка). Проза — только в теле.
Санкционированные внутрикарточные структуры (НЕ рёбра, разворачиваются компилятором): `participants`
(interface), `transitions` (state), `steps` (process), `stages` (production-system), `binding` (metric),
`reason-codes` (state). Новые top-level ключи frontmatter запрещены.

**0.3. Статусы.** Знание: `accepted | candidate | hypothesis | conflict | deprecated | unknown` —
эпистемическая лестница, ограничена trust floor источника. Decision: `proposed | accepted |
implemented | superseded | retired` — жизненный цикл, не уверенность. Неопределённость видима:
`unknown` / `not applicable`, пустых полей нет.

**0.4. Volatility → next-audit по умолчанию:** high = 7 дней (стадии CRM, конвенции метрик),
medium = 30 (процессы, роли), low = 180 (определения, границы бизнесов).

**0.5. Не хранится никогда:** PII, секреты, raw payloads, **значения объёмов/метрик**
(живые числа читаются по `binding` и существуют только как dashboard-reading source event
на момент анализа).

---

## 1. Категории и правило выбора типа

```
A. Объекты:   business · production-system · role · artifact · tool · metric
B. Динамика:  state · process · interface
C. Кинетика:  decision
D. Словарь:   term
```

**Русский словарь типов** (как агент говорит в чате и как термины употребляются в компании;
это глоссарий регистра коммуникации — одна модель, два рендера):

| Тип | Русское имя | Обиходно |
|---|---|---|
| business | бизнес | бизнес-юнит, направление |
| production-system | производственная система | поток, воронка, конвейер |
| stages (внутри ПС) | этап | этап воронки, стадия работы |
| process | **процесс** (= «бизнес-процесс» в обиходе) | регламентная работа ролей на этапе |
| state | жизненный цикл / состояния | путь сделки, путь участника |
| interface | передача | поставка, приёмка, handoff |
| decision | решение / правило / регламент-правило | СЛА, политика, конвенция |
| metric | метрика | показатель |
| artifact | предмет / результат | лид, сделка, встреча, карточка участника |
| tool | инструмент / система | Битрикс, дашборд, таблица |
| role | роль | КИ, продюсер, место (не человек) |
| term | термин | словарное слово |

**Разводка слова «бизнес-процесс».** В обиходе оно означает три разных уровня — модель
раскладывает их без нового типа:
1. *Процесс на этапе* («обработать поставку», «горячие пирожки») → `process`. Это и есть
   канонический «бизнес-процесс».
2. *Сквозной поток бизнеса* («от заявки до передачи в клуб») → НЕ process-карточка:
   это `production-system` с этапами + `state` (жизненный цикл артефакта). Карта процесса
   из плейбука — это state-machine, а не один процесс.
3. *Межбизнесовый поток* (Лидген → Привлечение → Клуб) → цепочка `interface`-карточек
   на карте компании (§8.5).

Дерево выбора при экстракции (мишень для агента):

1. Это слово/классификация, не сводимая к объекту? → `term`. Иначе объект получает карточку сам.
2. Это правило/решение/конвенция/практика («так делаем») → `decision` (различай `norm-kind`).
3. Это передача между ролями с критерием приёмки → `interface`.
4. Субъект — артефакт, меняющий режимы («лид проходит стадии») → `state`.
   Субъект — роль, делающая шаги («менеджер обзванивает») → `process`.
5. Это то, что производится/передаётся → `artifact`; чем меряют → `metric`; где живут
   факты → `tool`; кто (место, не человек) → `role`; машинерия из этапов → `production-system`;
   бизнес-юнит целиком → `business`.

---

## 2. Контракты типов

Формат: назначение → attrs-контракт → допустимые исходящие links → обязательные секции тела →
валидатор. Пример attrs — из Clubfirst.

### 2.1. `business` — бизнес («производит что-то для кого-то»)

Переименование v1 `module` → `business` по решению владельца (2026-07-02): каждый бизнес
(Привлечение, Продление, Лидген УС, ПАУ…) имеет **свою онтологию и свою модель**; слово
«модуль» уходит, чтобы не было недопонимания. Машинный алиас `module` оставлен
только для миграционной диагностики; начиная с пакета `0.10.0` строгая проверка
считает его ошибкой.

- **attrs:** нет собственных (вложенность — только рёбрами `part-of`; v1 `parent-module`/`submodules` упразднены).
- **links:** `produces → artifact`, `consumes → artifact|tool`, `owns → tool`, `part-of → business`, `measured-by → metric`, `governed-by → decision`.
- **Тело:** Purpose / What it produces / Who it produces for / Boundaries (что НЕ входит).
- **Валидатор:** business без `produces` — warning «бизнес без продукта» (аудит-паттерн v1 сохраняется).

```yaml
# biz-lidgen
links: { produces: [a-qualified-lead], owns: [t-bitrix24, t-amo], measured-by: [m-conv-meeting] }
```

### 2.2. `production-system` — машинерия бизнеса

- **attrs:**

| Поле | Тип | Обяз. | Смысл |
|---|---|---|---|
| `business` | biz-id | да | чья машинерия |
| `stages` | список структур | нет | **этап = связка**: `{state: st-id\|label, label?, processes: [p-ids], roles: [r-ids]}` — порядок значим |

  Этап — НЕ отдельный тип: это позиция конвейера, связывающая стадию артефакта с процессами
  и ролями на ней. Ровно ответ на «в Битриксе есть этапы, на этапах процессы, там входы-выходы-участники».
- **links:** `part-of → business`, `produces`, `consumes`, `measured-by`, `governed-by`.
- **Тело:** Inputs / Outputs / How it works (прозой) / Tools.
- **Валидатор:** каждый `stages[].state` резолвится; каждый `stages[].processes[]` резолвится
  и имеет `attrs.production-system == этот id`.

```yaml
# ps-bitrix
attrs:
  business: biz-lidgen
  stages:
    - { state: st-lead-lifecycle, label: "Звонок-знакомство", processes: [p-hot-pies, p-call-quality], roles: [r-qualifier] }
```

### 2.3. `role` — место с полномочиями (не человек)

- **attrs:** `kind: role|position` (да); `authority: []` (нет — список полномочий строками
  или d-ids). Люди не попадают в модель (PII); «роль→человек» живёт в рабочих системах.
- **links:** `governed-by → decision`, `part-of` — нет (роль не вкладывается; принадлежность
  выражается через participants интерфейсов и stages[].roles).
- **Тело:** Mandate (за что отвечает) / Is not (чем НЕ занимается).
- **Валидатор:** каждое `owner:` поле любой карточки обязано резолвиться в `role` или `unknown`.

### 2.4. `artifact` — предмет деятельности (то, что производится и передаётся)

- **attrs:** `kind: product | service | intermediate` (да).
- **links:** `lifecycle → state` (машина состояний этого артефакта), `measured-by → metric`,
  `source-of-truth → tool` (где живёт факт существования артефакта).
- **Тело:** Definition / **Is not** / Identity criteria (несущие секции v1-концепта переезжают сюда).
- **Валидатор:** artifact с `lifecycle` на state, чей `attrs.entity != этот id` — ошибка взаимности.

```yaml
# a-qualified-lead
attrs: { kind: intermediate }
links: { lifecycle: [st-lead-lifecycle], source-of-truth: [t-bitrix24] }
```

### 2.5. `tool` — инструмент/система (где живут факты)

- **attrs:** `kind: system | tool | dashboard` (да); `access-mode` (нет).
- **links:** `governed-by`.
- **Тело:** What it holds (какие факты здесь истинны) / Owner side.
- **Валидатор:** цель всякого `source-of-truth` — только tool.

### 2.6. `metric` — контракт измерения ⭐ (кормит coach/stockflow/leverage/why-tree)

- **attrs:**

| Поле | Тип | Обяз. | Смысл |
|---|---|---|---|
| `formula` | строка | да (`unknown` допустим, но виден) | как считается — человекочитаемо, но точно |
| `unit` | строка | да | %, шт/нед, ₽ |
| `direction` | `up-is-good\|down-is-good\|target-band` | да | без этого leverage-finder слеп |
| `target` | число+unit | нет | цель (для gap-vs-goal why-tree) |
| `baseline` | `{value, as-of, source-event}` | нет | замороженный evidence brief, НЕ живое число |
| `refresh-cadence` | строка | нет | как часто пересчитывается |
| `binding` | `{source: source-id, locator, field}` | да либо `unknown` | ГДЕ читать значение; самих значений в модели нет |

- **links:** `source-of-truth → tool` (обязателен либо явный unknown — «метрика без истины» = аудит-дефект v1), `governed-by → decision` (конвенция измерения).
- **Тело:** Meaning / Known distortions (как её обманывают).
- **Валидатор:** metric без `source-of-truth` и без `governed-by` на measurement-convention → warning.

```yaml
# m-conv-meeting
attrs:
  formula: "встречи проведённые / лиды взятые в работу"
  unit: "%"
  direction: up-is-good
  target: "35%"
  baseline: { value: "28%", as-of: 2026-06-30, source-event: srcevt-btx-0630 }
  binding: { source: src-bitrix24, locator: "воронка Лидген", field: "количество сделок на стадии" }
```

### 2.7. `state` — машина состояний артефакта ⭐ (кормит coach/stockflow, вьюер-lifecycle, archify)

- **attrs:**

| Поле | Тип | Обяз. | Смысл |
|---|---|---|---|
| `entity` | artifact-id | да | чью жизнь описывает |
| `states` | [строк] | да | закрытый список режимов |
| `entry` | [строк⊆states] | да | входные |
| `terminal` | [строк⊆states] | да | конечные (Корзина — здесь, а не regex по названию!) |
| `transitions` | список структур | да | `{from, to, trigger, sla?, authority?: r-id\|d-id, evidence?}` — sla = задержка для systems-coach; authority = «кто вправе объявить переход» (кинетика v1 сохраняется) |
| `reason-codes` | список структур | нет | справочник обязательных кодов перехода: `{on: <terminal-state>, codes: [{code, meaning, what-to-do?}]}` — причины проигрыша Корзины живут ЗДЕСЬ; доли/объёмы — live-оверлей |

- **links:** `source-of-truth → tool` (где стадия истинна — Битрикс), `measured-by`, `governed-by`.
- **Тело:** Transition evidence (что считается доказательством перехода) / Who may declare done.
- **Валидатор:** все from/to ∈ states; entry без входящих; terminal без исходящих;
  transitions с sla — парсябельный срок; `reason-codes[].on` ∈ terminal.

```yaml
# st-lead-lifecycle (фрагмент)
attrs:
  entity: a-qualified-lead
  entry: ["Готов ко встрече"]
  terminal: ["Активация", "Корзина"]
  transitions:
    - { from: "База входящая", to: "Звонок-знакомство", trigger: "взять в работу", sla: "24ч раб.", authority: r-qualifier }
  reason-codes:
    - on: "Корзина"
      codes:
        - { code: "не-целевой", meaning: "не проходит по критериям сегмента", what-to-do: "вернуть в маркетинг с пометкой" }
        - { code: "недозвон", meaning: "2 звонка + 1 смс без ответа" }
```

### 2.8. `process` — упорядоченная работа ролей ⭐ (кормит constraint-finder, вьюер-flowchart, archify-workflow)

- **attrs:**

| Поле | Тип | Обяз. | Смысл |
|---|---|---|---|
| `production-system` | ps-id | да | где живёт |
| `entry-state` / `exit-state` | `{state: st-id, name}` | нет | стыковка с жизнью артефакта |
| `steps` | список структур | да | `{id, role: r-id, does, input?: a-id\|строка, output?: a-id\|строка, rule?: d-id, decision?: {question, yes: step-id, no: step-id}, warn?: true}` — **порядок значим (verbatim для ToC)**; `rule` на шаге = политика шага (главная экстракция constraint-finder); `warn` = «не ясно, что дальше» |

- **links:** `measured-by`, `governed-by → decision` (регламент процесса целиком; регламент-документ — источник, правило из него — decision).
- **Тело:** Trigger / Exceptions / Where it breaks (as-is честность).
- **Валидатор:** steps[].role резолвится; decision.yes/no указывают на существующие step-id;
  ациклический счёт шагов ≤ 30 (бюджет визуализации — дальше drill-down).

### 2.9. `interface` — передача между ролями/бизнесами (гиперребро, теперь с градацией)

Интерфейсы разные по весу: где-то передача заканчивается результатом, где-то (Лидген УС ↔
Привлечение) несёт SLA, качества поставки и правила приёмки. Градация — поле `contract`:

- **attrs (общие, оба уровня):**

| Поле | Тип | Обяз. | Смысл |
|---|---|---|---|
| `contract` | `handoff \| contract` | да | вес интерфейса |
| `participants` | `{supplier: [r-ids\|biz-ids], customer: [r-ids\|biz-ids], subject: [a-ids]}` | да | стороны и предмет; между бизнесами допустимы biz-id |
| `outcome` | строка | да | что считается состоявшейся передачей |
| `quality-criterion` | строка | `contract`: да; `handoff`: нет | как заказчик понимает, что принял |

- **attrs (только `contract: contract`):**

| Поле | Тип | Смысл |
|---|---|---|
| `qualities` | `[{name, definition, sla?}]` | качества поставки («Готов ко встрече», «Готов к мероприятию»…) |
| `slas` | `[{id, rule, breach-effect}]` | независимые SLA (SLA-1/2/3; «нельзя склеивать»); breach-effect может ссылаться на `transitions[].effect` (автопокупка) |
| `acceptance` | `{who, criteria, moment, rejection, return-policy}` | приёмка: кто, по чему, когда наступает, право отклонить (даже после оплаты), правила возврата |

- **links:** `governed-by`. `supplies-to` авторски НЕ пишется — порождается декомпозицией.
- **Валидатор:** id строго `if-<slug>`, не из имён участников; participants резолвятся;
  `contract: contract` без `acceptance` — ошибка; `handoff` с заполненными `slas` — warning
  «похоже, это contract» (линт-повышение).
- **Компилятор:** разворачивает в `has-supplier`/`has-customer`/`has-subject` + `supplies-to`.
- **Владение и зеркала между бизнесами:** §8.4.

### 2.10. `decision` — кинетика (правила, решения, конвенции, практики)

- **attrs:** 12 полей v1 **дословно** (`irreversible, episode, scope, decision-owner,
  transition-authority, measurement-convention, affected-workflows, affected-kpis,
  propagation-sla, override-policy, exception-path, blast-radius`) **плюс:**

| Новое поле | Тип | Обяз. | Смысл |
|---|---|---|---|
| `norm-kind` | `decided \| regulated \| observed-practice` | да | решено / из регламента / наблюдаемая практика без автора |
| `supersedes` / `superseded-by` | d-id | нет | цепочка замен (мета-связь — в attrs, не в links) |
| `valid-from` / `valid-to` | date | нет | окна действия |

- **Правила norm-kind:** `regulated` требует source с kind регламента; `observed-practice`
  требует `transition-authority: unknown` и статус ≤ candidate (практика не может родиться accepted).
- **Тело:** Decision / Episode / Scope / Consequences / Kinetic checks / **Considered alternatives**
  (новая секция: отвергнутые варианты + почему) / Supersession-rollback.
- **Валидатор:** decision-owner резолвится в role|unknown; affected-kpis → metric-ids;
  affected-workflows → process/interface-ids; superseded ⇒ superseded-by заполнен.

### 2.11. `term` — словарная карточка (только не-объекты)

- **attrs:** `applies-to: [ids]` (да — к каким объектам слово применяется).
- **Тело:** Definition / Is not / Identity criteria.
- **Валидатор-эвристика (warning):** если term по applies-to указывает ровно на один объект —
  подозрение «это должна быть секция объекта, не отдельная карточка».

---

## 3. Отношения: матрица (10, закрытый список)

| # | Отношение | От → К | Кардин. | Авторство | Рёберные attrs |
|---|---|---|---|---|---|
| 1 | `produces` | business/PS/process → artifact | N:M | авторское | — |
| 2 | `consumes` | business/PS/process → artifact/tool | N:M | авторское | — |
| 3 | `supplies-to` | role → role | N:M | **derived** из interface; авторское — только как interface-кандидат (линт: появился критерий приёмки → промоутируй в if-) | `{interface, subject}` |
| 4 | `part-of` | business/PS → business/PS | N:1 | авторское (ребёнок→родитель) | — |
| 5 | `owns` | business → tool | 1:N | авторское; **запрещён** при существующем part-of той же пары | — |
| 6 | `measured-by` | business/PS/process/artifact/state → metric | N:M | авторское | — |
| 7 | `source-of-truth` | metric/state/artifact → tool | N:1 | авторское | — |
| 8 | `lifecycle` (экс-`in-state`) | artifact → state | 1:N | авторское; алиас `in-state` только для миграционной диагностики; 0.10.0+ strict = ошибка | — |
| 9 | `governed-by` | business/PS/role/process/state/metric → decision | N:M | авторское; уровень шага — через `steps[].rule` | — |
| 10 | `influences` ⭐ | metric/state/artifact → metric/state/artifact | N:M | авторское, evidence обязателен | `{polarity: +\|-, delay?: срок}` |

**Derived-рёбра компилятора (в карточках не пишутся):** `has-supplier`/`has-customer`/`has-subject`
(из interface), все инверсии (produced-by, part-контейнеры…), `step-edges` (из process.steps),
`stage-edges` (из ps.stages), **loops** (циклы в influences-подграфе → R/B-петли с проведёнными путями
для systems-coach).

**Эпистемика influences:** claimKind=agent-inference ⇒ статус ребра ≤ hypothesis (существующее
правило тройки распространяется на рёбра). Trade-off для TRIZ = узел с двумя influences разной
полярности + conflict-карточка.

---

## 4. Кросс-правила валидатора v2 (сводно)

- V1. Один авторский направленный факт — одно ребро; инверсии только derived; owns+part-of одной пары — ошибка.
- V2. Endpoint-типизация всех 10 отношений по матрице §3.
- V3. `owner` → role-id|unknown; `source` → source map; `evidence[]` → `srcevt-*|prop-*`.
- V4. Attrs-контракт закрыт по типу: чужой ключ — ошибка (контракт живёт в schemas/, не только в docs).
- V5. Взаимность: artifact.lifecycle ↔ state.entity; ps.stages[].processes[] ↔ process.attrs.production-system.
- V6. Внутрикарточные ссылки (steps[].role, transitions[].authority, reason-codes[].on, stages[].state) резолвятся.
- V7. Статус ≤ trust floor источника (v1, без изменений). Плюс: observed-practice ≤ candidate.
- V8. Терминальность/входы состояний — из полей entry/terminal, не из эвристик по названию.
- V9. Бюджеты: process.steps ≤ 30; state.states ≤ 12 (дальше — decompose, это сигнал модели, не рендера).

---

## 5. Приёмка: кого кормят поля (проверяется воротами, не токенами)

| Потребитель | Требует | Даёт v2 |
|---|---|---|
| ai-systems-coach | stocks, flows, петли, задержки, цель | artifact+state(+binding-снимок), transitions, циклы influences, transitions[].sla + influences[].delay, metric.target |
| ai-stockflow-builder | stocks+начальные, потоки-формулы, параметры, reference mode, Gate 0 противоречие | baseline{value,as-of}, metric.formula, influences±, conflict-карточка |
| leverage-finder | цель-как-сток, enacted goal, accountability gaps | metric(target,direction), decision(norm-kind: что реально вознаграждается), steps[].role vs measured-by (кто управляет потоком/видит сток) |
| constraint-finder | шаги verbatim, политики на шагах, WIP, цель в T | process.steps (порядок), steps[].rule → decision, WIP = live-снимок по binding, business produces + m-* |
| triz-dissolve | trade-off X↑Y↓, ресурсы | пара influences разной полярности + conflict; tool/role-инвентарь |
| why-tree | apex gap-vs-goal, answer-kinds, citations | metric.target−baseline+даты, evidenceGrade (совпадает 1:1), evidence[] на карточке |
| Вьюер | компонент по типу | state→lifecycle-доска, process→флоучарт, ps.stages→контейнеры, metric→карточка+live, reason-codes→таблица |
| Archify-экспорт | бюджеты шаблонов | lifecycle: ≤5 фаз/3 ожид./3 исхода → маппер сворачивает по entry/terminal/waiting; workflow: lanes = steps[].role |

Ворота `evaluate_system_analysis_readiness` переводятся с поиска токенов на проверку
именно этих полей (missingFields = конкретные имена из контрактов §2).

---

## 6. Миграция v1 → v2 (id не меняются — ссылки переживают)

| v1 | v2 |
|---|---|
| concept subtype product/service | artifact (kind=product/service) |
| concept subtype metric | metric (formula/unit/… добираются, до тех пор `unknown`) |
| concept subtype role/position | role |
| concept subtype tool/system | tool |
| concept subtype regulation/rule/authority | decision (norm-kind: regulated) |
| concept subtype state | слить с state-карточкой (дубликат → ревью) |
| concept subtype module | дедупликация с business |
| type: module | type: business (алиас module — только для миграционной диагностики; 0.10.0+ strict = ошибка) |
| concept subtype fact/other | очередь ревью: term / artifact — решает человек |
| attrs.parent-module / submodules | рёбра part-of |
| link `in-state` | `lifecycle` (алиас только для миграционной диагностики; 0.10.0+ strict = ошибка) |
| state-карточки-«этапы» (как в сэмпле) | стадии в st-*.states + ps.stages[] |
| decision: 12 attrs | те же 12 + norm-kind (дефолт decided) |

Шаги: (1) decision-карточка об изменении контракта (самодемонстрация); (2) schemas v2 + валидатор;
(3) `scripts/migrate_taxonomy_v2.py` на examples/ (спорное — в ревью); (4) эталонный бизнес
examples/ на v2 — включая **пример process** и петлю influences; (5) евалы зелёные; (6) прогон
ворот 6 скиллов на эталоне — приёмка.

---

## 7. Решения, которые чеканишь ты (агент не вправе)

1. **Префиксы id** (§0.1): обязательные для новых карточек или рекомендация? (Моя рекомендация: обязательные для новых, старые не трогаем.)
2. **`influences` сейчас или волной 2?** Он тянет за собой компилятор петель. (Рекомендация: схему и валидатор — сейчас, компилятор петель — волной 2; авторские рёбра уже копятся.)
3. **`term` на старте или позже?** Можно стартовать 10 типами и добавить term решением, когда появится первое спорное не-объектное слово. (Рекомендация: сразу — дёшев, а спорные слова появятся в первой же сессии.)
4. **Судьба `sequence`-жанра:** передачи как archify-sequence требуют порядка сообщений, которого в модели нет (interface — вне времени). Добавлять ли в process.steps направление «кому» для sequence-рендера? (Рекомендация: нет, не сейчас — не плодить поля без потребителя.)

---

## 8. Масштабирование на несколько бизнесов (конфигуратор)

Модель обязана переживать не только Привлечение, но и Продление, Лидген УС, ПАУ —
**у каждого бизнеса своя онтология и своя модель**. Правила:

**8.1. Закрытые списки — словарь-потолок, а не чек-лист.** 11 типов и 10 отношений — это
категории *деятельности вообще* (производство, потребление, передача-с-приёмкой, вложенность,
измерение, местоположение истины, жизненный цикл, управление, причинность), а не категории
Привлечения. Бизнес использует **подмножество**; отсутствие отношения у бизнеса — не дефект.
Специфика бизнеса живёт в содержании карточек и attrs, а не в новых типах.

**8.2. Прогноз по бизнесам (проверить стресс-тестами):**
- *Лидген УС*: источники трафика (tool/artifact), кампании (process), стоимость лида (metric),
  качества поставки — уже на `if-lidgen-attraction`. Специфических отношений не предвидится.
- *Продление*: членство (artifact) с lifecycle (активно → к продлению → продлено/отток),
  time-based триггеры («за 60 дней до окончания» — `transitions[].trigger`), отток =
  terminal + reason-codes, драйверы продления = `influences`, тарифы = decision + term.
- *ПАУ*: участники = роли (без PII), вовлечённость = metrics + live-оверлей, форматы =
  process с target-effect (патч Д3); ПАУ **поставляет форматы Привлечению** — это interface
  (supplier: ПАУ, customer: Привлечение, subject: проведённый формат), не новое отношение.

**8.3. Фальсифицируемость таксономии.** Новое отношение вводится только решением
(протокол v1) и только если: (а) это отношение бизнес-реальности, не мета; (б) по нему
нужны запросы между бизнесами; (в) оно не выражается attrs/интерфейсом. **Если один бизнес
требует >2 новых отношений — таксономия неверна, чиним её, а не расширяем список.**

**8.4. Интерфейсы между бизнесами: градация контракта + правило владения.**
Интерфейсы разные по весу — это поле `contract` в §2.9:
- `handoff` — заканчивается передачей результата: supplier/customer/subject + outcome,
  без SLA и формальной приёмки (пример: заявки с сайта → Лидген);
- `contract` — полный контракт, как Лидген УС ↔ Привлечение: качества поставки, несколько
  SLA с последствиями нарушения (автопокупка), правила приёмки/возврата, момент расчёта.

Где живёт if-карточка (по DEMO — приёмку определяет заказчик):
- if-карточкой **владеет бизнес-заказчик** (его критерий приёмки, его качества);
- бизнес-поставщик держит **зеркало-стаб** с тем же id, `source: <онтология заказчика>`,
  без права редактировать критерии;
- id интерфейсов — **глобальный неймспейс** компании (уникальны across бизнесов);
- валидатор межбизнесового слоя сверяет зеркала с оригиналами (drift зеркал = ошибка).

**8.5. Карта компании — тонкий слой конфигуратора.** Над онтологиями бизнесов — одна
карта уровня компании: **только** business-карточки (чёрные ящики) + if-карточки + сквозные
metric-агрегаты. Внутренности чужого бизнеса не моделируются (подтверждено Привлечением:
«не описывает внутреннюю механику Лидген УС»). Это и есть поли-системность СМД: бизнесы —
независимые системы, интерфейсы — конфигуратор, который их сшивает; владелец компании смотрит
на карту, владелец бизнеса — в свой бизнес.

---

## 9. Аудит полноты против классических рамок (финальный вердикт)

Проверка против ArchiMate 3.x business layer, REA (resources-events-agents), DEMO,
BIZBOK (capability/value stream), Business Model Canvas.

### 9.1. Покрытие

| Рамка требует | В v2 |
|---|---|
| ArchiMate: Actor / Role | `role` (актор-наполнение сознательно вне модели — PII; «роль→человек» в рабочих системах) |
| ArchiMate: Process / Function | `process`; функция бизнеса = Purpose + produces |
| ArchiMate: Interaction / Collaboration | `interface` (наш сильнее: приёмка, качества, SLA); совместность ролей = participants, stages[].roles |
| ArchiMate: Business Object / Product | `artifact` (kind: product/service/intermediate) |
| ArchiMate: Contract | `interface.contract` + acceptance (градация §2.9) |
| ArchiMate: Service | artifact kind=service + interface (exposed behavior) |
| ArchiMate: Representation | source map (документ = источник, не объект модели) |
| REA: Agents / Resources | business, role / artifact, tool |
| REA: Events (state changes) | `state.transitions` (+ `transitions[].effect` — стык с интерфейсом) |
| REA: commitments (extended) | interface.slas + acceptance |
| DEMO: транзакция с приёмкой | interface — ядро модели |
| BIZBOK: capability | production-system (способность видна через машинерию — as-is принцип) |
| BIZBOK: value stream | сквозной поток = PS + lifecycle + цепочка интерфейсов (§1, разводка «бизнес-процесса») |
| BMC: сегменты / каналы | сегменты = `term` (наблюдаем); каналы — см. 9.2 |
| BMC: выручка / затраты | сознательно в оверлее (юнит-экономика — отчёт, не модель; финконтракт — references/overlay) |
| Системная динамика | `influences` (полярность/задержка) + derived-петли |

### 9.2. Точечные добавки по результатам аудита (принять)

1. **Канал** — `tool.kind` += `channel` (СБЕР ВСП, Партнёрка, Диджитал — каналы поставки;
   всплыли в стресс-тесте как sources потоков). Без нового типа.
2. **REA-duality (обмен)** — `interface.acceptance.settlement` (опц.): что переходит взамен
   в момент приёмки («оплата поставки по тарифу», metric-id цены). Автопокупка становится
   полной REA-парой «поставка ↔ оплата» без затаскивания финмодели в онтологию.

### 9.3. Watch-list — НЕ вводить, пока нет запросов (критерий §8.3)

| Кандидат | Сейчас выражается | Вводить типом, когда |
|---|---|---|
| Цель (goal/OKR) | metric.target + decision о цели + Purpose | появятся запросы «какие процессы служат цели X» |
| Бизнес-событие (ArchiMate event) | transitions[].trigger + process(target-effect) | события начнут связывать несколько машин состояний |
| Риск | open question / hypothesis-карточка + sourceRisk | появится реестр рисков с владельцами и ревизиями |
| Оргиерархия ролей | сознательно нет: authority вместо подчинения | понадобятся запросы по цепочке эскалации |

### 9.4. Вердикт

Модель **достаточна для построения модели данных компании и понимания её устройства**
на операционном уровне (as-is деятельность: кто, что, как, в каких состояниях, кто решает,
чем меряется, что кому передаётся и на каких условиях). Покрытие классических рамок полное
либо расхождение объяснимо сознательным исключением (PII, объёмы, финмодель, стратегия-как-
намерение). Пропущенных несущих элементов аудит не выявил; два точечных добавления (9.2)
приняты, четыре кандидата (9.3) отложены с явными критериями введения. Дисциплина роста:
§8.3 — новые элементы только решением, >2 новых отношений на один бизнес = сигнал чинить
таксономию.
