# Plan 005 (v2, переписан 2026-07-05): Онбординг вместо воркшопа — playbook трёх блоков + скиллы onboard-contour и show-model

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Commit in worktree. SKIP updating plans/README.md — reviewer
> maintains the index. Audit every claim against actual tool results.
>
> **Drift check (run first)**: `grep -n "Mine baseline materials" agent-os/OPERATING_LOOP.md`
> и `grep -n "After the boundary is clear" adapters/openclaw/FIRST_MESSAGE.md` —
> обе строки должны существовать; иначе STOP (first-session контракты уже переписаны).

## Status

- **Priority**: P1 (следующий релиз) | **Effort**: M | **Risk**: LOW (доки+скиллы, кода нет)
- **Depends on**: none | **Category**: docs + dx
- **Planned at**: commit `2e4a671`, 2026-07-05
- **Заменяет**: первую версию этого плана (воркшоп 60–90 мин) — решение владельца
  2026-07-05: первая сессия = онбординг 15–25 минут; моделирование — фоновая работа.

## Why this matters

Старый контракт первой сессии — интервью-воркшоп: человек 60–90 минут работает
источником (майнинг при нём, capture loop по 5 мин на карточку). Владелец решил
иначе: первая сессия = **онбординг за 15–25 минут** — контур (8 вопросов + 1
подтверждение) → подключение источников → договор о ритме, а модель агент строит
сам, фоном, из подключённых источников. Это mine-first, доведённый до конца.

## Current state

- `agent-os/OPERATING_LOOP.md` — First-session loop (9 шагов, «Mine baseline
  materials provided by the human», «Ask one model question at a time»).
- `adapters/openclaw/FIRST_MESSAGE.md:35-37` — «After the boundary is clear, ask
  for Telegram daily scan time, Fireflies enablement…» (противоречит OPERATING_LOOP
  шагу 9 «Only after the first session»).
- `adapters/openclaw/BOOTSTRAP.md` — 7 шагов, шаг 5 задаёт первый вопрос о границе,
  шаг 7 — вьюер.
- `skills/` — 13 скиллов; `connect-source` существует (Блок B опирается на него);
  скиллов `onboard-contour` и `show-model` нет.
- `templates/workspace/HUMAN_README.md.tpl` — только вопрос о границе.
- Нормативный источник дизайна (на этой машине):
  `/Users/vladislavbogdan/Онтология тест/ВЗАИМОДЕЙСТВИЕ-резидент-владелец.md`
  (§0, §1 Фаза 0, §4 форматы) — ПРОЧИТАТЬ ПЕРВЫМ. Ключевое инлайнится ниже.

**Лестница Блока A (нормативно):** (1) чем занимается компания, одним абзацем;
(2) что производите/продаёте и кому; (3) какие направления/бизнесы внутри;
(4) что сейчас болит сильнее всего; → **рекомендация агента, не вопрос**: «Начну
разбираться с [X] — там [боль/источник]. Ок?»; (5) что главное «течёт» через это
направление; (6) где живёт правда о нём; (7) ключевые роли; (8) метрика «идёт
хорошо». Ответы → candidate-карточки сразу. Review-owners НЕ спрашиваются
(владелец — единственный ревьюер на старте). В начале блока агент проговаривает:
«можешь отвечать голосовыми — я расшифровываю, в голосе больше контекста»
(OpenClaw отдаёт voice как транскрипт из коробки).

**Exit-критерии онбординга:** контур зафиксирован (business + предмет +
инструменты-истины candidate) · ≥1 источник connected (connected/pending/declined —
«обещано» не считается) · ритм записан в workspace-конфиг · кроны запланированы ·
владелец предупреждён об объёме разгона.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK (303) |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 30/198, 0 failed |

## Scope

**In scope:** `agent-os/FIRST_SESSION_PLAYBOOK.md` (создать),
`skills/onboard-contour/SKILL.md` (создать), `skills/show-model/SKILL.md` (создать),
`adapters/openclaw/FIRST_MESSAGE.md`, `adapters/openclaw/BOOTSTRAP.md`,
`agent-os/OPERATING_LOOP.md` (First-session loop секция),
`templates/workspace/HUMAN_README.md.tpl`, `skills/README.md` (список скиллов).

**Out of scope:** кроны/ритм (план 008), группы/скан (009), Skribby (010),
`skills/business-ontology/SKILL.md` hard rules (не трогать), COMMUNICATION_POLICY.

## Git workflow

- Ветка от main: `feature/onboarding-playbook`; коммит на шаг; английский для
  файлов репо (реплики-шаблоны агенту — двуязычно не надо: политика «язык
  пользователя в чате» уже в COMMUNICATION_POLICY; шаблоны пишутся по-английски
  с пометкой «render in the user's language»).

## Steps

### Step 1: FIRST_SESSION_PLAYBOOK.md
`agent-os/FIRST_SESSION_PLAYBOOK.md`: онбординг 15–25 мин, три блока —
Block A Contour (лестница выше, входная фраза про голосовые, каждый ответ →
candidate через propose-change), Block B Sources (через skills/connect-source;
статусы connected/pending/declined; минимум 1 connected), Block C Rhythm
(отсылка к плану 008: дефолт daily-digest 09:00, без срочной полосы, окно тишины
22–09; здесь только договорённость и предупреждение об объёме — механика кронов
в SCHEDULING.md). Exit-критерии (выше). Приложения: Deep-dive workshop (старый
60–90-мин сценарий, опциональный) и Interview-fallback (источников нет: владелец =
источник owner-interview, всё candidate).
**Verify**: `grep -c "Block" agent-os/FIRST_SESSION_PLAYBOOK.md` ≥ 3;
`grep -n "voice" agent-os/FIRST_SESSION_PLAYBOOK.md` ≥ 1.

### Step 2: skills/onboard-contour/SKILL.md
По структуре соседних скиллов (посмотри skills/connect-source/SKILL.md):
description, when to use (первая сессия, Block A), the ladder (8 вопросов +
рекомендация старта — выбор агента из ответов 3+4 и подключаемых источников),
правила (один вопрос за раз; короткие ответы — не выжимать детали; каждый ответ
сразу в staged; голос приветствуется; review-owners не спрашивать), what good
looks like + 2 поведенческих кейса (владелец ответил на всё одним голосовым →
разобрать на карточки и подтвердить списком; владелец не знает ответа → unknown,
дальше).
**Verify**: файл существует; `python3 scripts/run_evals.py --fixture-only` → 0 failed
(евал openclaw-clean-root не должен сломаться от нового каталога скилла — если
ломается, STOP и доложить).

### Step 3: skills/show-model/SKILL.md
Показ модели: первично — ссылка на вьюер, постоянно развёрнутый на сервере агента
(deep-link `#card/<id>`, `#map`); fallback — текстовая витрина в чат
(«название — тип — статус — определение одной строкой», ≤10 карточек за раз).
Когда вызывать: wrap-up онбординга, после принятого пакета, по запросу «покажи».
**Verify**: файл существует, ссылается на viewer/README.md.

### Step 4: Правки контрактов
- `adapters/openclaw/FIRST_MESSAGE.md`: «After the boundary is clear, ask for
  Telegram daily scan time…» → «Run the onboarding per
  agent-os/FIRST_SESSION_PLAYBOOK.md (contour → sources → rhythm)…»; смысл:
  source-setup — это Block B самой сессии, сканы стартуют после.
- `adapters/openclaw/BOOTSTRAP.md` шаг 5-6: первый вопрос — не граница, а Block A
  ladder (ссылка на playbook); шаг 7 (вьюер) → вызов show-model в wrap-up.
- `agent-os/OPERATING_LOOP.md` First-session loop: 9 шагов → три блока playbook
  (сохранить: mine-first для присланного, propose-only, никакого промоушена).
- `templates/workspace/HUMAN_README.md.tpl`: первый вопрос заменить на короткое
  описание онбординга (3 блока, 15–25 минут, можно голосом).
**Verify**: `grep -rn "FIRST_SESSION_PLAYBOOK" adapters/ agent-os/ | wc -l` ≥ 3;
`grep -c "After the boundary is clear, ask for Telegram" adapters/openclaw/FIRST_MESSAGE.md` → 0.

### Step 5: Согласованность и прогон
`skills/README.md`: добавить два новых скилла в список. Полный прогон тестов и
евалов.
**Verify**: `python3 -m unittest discover -s tests -q` → OK;
`python3 scripts/run_evals.py --fixture-only` → 0 failed.

## Test plan

Кода нет — прогон существующих тестов/евалов (Step 5) + grep-verify каждого шага.
Поведенческие кейсы новых скиллов — в самих SKILL.md (исполняются людьми/judge,
как у остальных 13).

## Done criteria

- [ ] Playbook + 2 скилла существуют, все grep-verify проходят
- [ ] Противоречие FIRST_MESSAGE/OPERATING_LOOP устранено
- [ ] `python3 -m unittest discover -s tests -q` → OK
- [ ] `python3 scripts/run_evals.py --fixture-only` → 0 failed
- [ ] ≥4 коммита

## STOP conditions

- Структура SKILL.md соседей радикально другая (нет description/when-to-use) —
  доложить фактический формат.
- Eval `openclaw-clean-root` или `methodology-regression-contracts` падает от
  правок адаптера/agent-os — доложить, фикстуры не править.

## Maintenance notes

- План 008 подключает Block C к реальным кронам; 009/010 — группы и Skribby.
- Старый воркшоп жив как приложение playbook — не удалять при будущих правках.
