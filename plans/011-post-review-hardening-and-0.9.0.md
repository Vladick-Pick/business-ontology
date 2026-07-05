# Plan 011: Дожать после ревью — зафиксировать fix-батч, закрыть находки, CI, релиз 0.9.0

> **Executor instructions**: Follow step by step; verify each step; on STOP —
> stop and report. Работа идёт В ЭТОМ рабочем дереве (в нём твой незакоммиченный
> fix-батч — его нельзя потерять), НЕ в чистом clone/worktree. SKIP updating
> plans/README.md — кроме Step 8, где это явная задача.
>
> **Drift check (run first)**: `git branch --show-current` → `chore/plan-011-hardening`;
> `git status --short | wc -l` → ~15 (13 modified + 2 untracked + этот план);
> `python3 -m unittest discover -s tests -q` → OK (331 на момент написания).
> Если дерево уже чистое и изменения запушены — Step 0 пропустить, остальное
> сверить по Verify каждого шага (часть могла быть сделана) и делать только
> недостающее.

## Status

- **Priority**: P1 | **Effort**: M-L | **Risk**: LOW-MED
- **Depends on**: PRs #15–#18 merged (даны) | **Category**: hardening + docs + release
- **Planned at**: commit `96f37ed` (main == origin/main), 2026-07-06
- **Контекст**: ревью реализации PRs #15–#18 (два фокуса: код + методология)
  выдал 1 BLOCKER + 6 HIGH + MEDs. Часть находок уже исправлена в незакоммиченном
  WIP этого дерева (курсор, редакция webhook-query, agent-proof раннер,
  readiness-метки). Этот план: зафиксировать WIP → закрыть остальное → CI →
  релиз 0.9.0.

## Why this matters

main = «несобранный 0.9.0»: весь слой взаимодействия вмержен, но не зарелижен,
а исправления по ревью живут только в рабочем дереве одной машины — одно
неловкое движение, и они потеряны. Плюс live-test-кит до сих пор описывает
СТАРЫЙ флоу (Fireflies, gog, всё-в-одну-сессию) — оператор, запускающий живой
тест по этим докам, будет валидировать не ту систему, которую мы построили.

## Current state (проверено 2026-07-06 на живом дереве)

- WIP (не закоммичен): `git status --short` — 13 M + 2 ?? (`scripts/run_extraction_agent_proof.py`,
  `tests/test_run_extraction_agent_proof.py`). Тесты с ним зелёные: 331 OK.
  Содержание: strict ts-then-id курсор в `tg_collect_daily.py:239`; редакция
  sensitive query keys (`token/key/secret/signature`) в webhook_url
  (`skribby_order_bot.py`, `dry_run_payload`); agent-proof раннер + правки
  `run_extraction_benchmark.py` и `evals/golden/README.md`; «Runtime readiness
  labels» (setup-only/source-connected/scheduled/live-proven) в
  `agent-os/FIRST_SESSION_PLAYBOOK.md:69` + `templates/workspace/LIVE_TEST_STATUS.md.tpl`
  + `scripts/bootstrap_openclaw_workspace.py` + тесты.
- BLOCKER открыт: `docs/openclaw-live-experiment.md:87–92` (шаги «ask for
  Telegram groups, daily scan time… Fireflies… gog» одной сессией) и весь
  `adapters/openclaw/live-test/` (Fireflies в LIVE_TEST_FIRST_MESSAGE.md:26,
  README.md:11, OPERATOR_CHECKLIST.md:21,33, PASS_FAIL_GATES.md:15,
  OBSERVER_PROTOCOL.md:13,25, AUTHORIZATION_RUNBOOK.md:49) — старый флоу.
  Новый флоу: `agent-os/FIRST_SESSION_PLAYBOOK.md` (3 блока, 15–25 мин),
  группы по `adapters/openclaw/TELEGRAM_GROUPS.md`, суточный инжест
  (`skills/daily-ingest`), Skribby (`adapters/openclaw/MEETING_TRANSCRIPTS.md`)
  вместо Fireflies.
- Недефинированный tier «permission» в high-risk перечне — 3 места:
  `agent-os/REVIEW_PROTOCOL.md:42`, `adapters/openclaw/TELEGRAM_GROUPS.md:71`,
  `skills/daily-ingest/SKILL.md:47`. Канонический верхний tier по
  `specs/REVIEW-SPEC.md` — source-of-truth / authority / measurement-convention.
- Channel authority: секция есть ТОЛЬКО в `agent-os/REVIEW_PROTOCOL.md`
  (grep -ci "channel authority": agent-os=1, adapters/openclaw/REVIEW_PROTOCOL.md=0,
  templates/workspace/REVIEW_PROTOCOL.md.tpl=0). Евалов на неё нет
  (`ls evals/cases/*.json | wc -l` → 30, ни один не про авторитет канала).
- PII-контракт коллектора: `scripts/tg_collect_daily.py:354` — `_redact` режет
  только контакты (`CONTACT_RE` → `[redacted-contact]`); имена/handles
  отправителей СОХРАНЯЮТСЯ (`:225`). `adapters/openclaw/source-setup/telegram-scan.md`
  пункт 7 требует «PII rules for names, handles…», но дефолт не зафиксирован.
- SKRIBBY_API_KEY: плоское имя в `adapters/openclaw/MEETING_TRANSCRIPTS.md:24` и
  `adapters/openclaw/source-setup/skribby.md:38` — заявленная изоляция «свой ключ
  у каждого агента» нигде не объяснена механизмом.
- `adapters/openclaw/SCHEDULING.md:12–16`: примеры мешают `cron create` и
  `cron add`, alias-заметка есть на :16.
- CI отсутствует (`.github/workflows/` нет).
- `plans/README.md`: строки 005/006/008/009/010 всё ещё TODO, хотя вмержены
  PRs #15–#18.
- Релиз: `docs/release-process.md:111` — опубликован 0.8.0, следующий драфт 0.9.0;
  версия скилла `skills/business-ontology/SKILL.md:5` = "0.8.0".

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Тесты | `python3 -m unittest discover -s tests -q` | OK |
| Евалы | `python3 scripts/run_evals.py --fixture-only` | 0 failed |
| Статус | `git status --short` | пусто после Step 0 |

## Scope

**In scope:** коммит WIP; `docs/openclaw-live-experiment.md` +
`adapters/openclaw/live-test/*` (реалайн под новый флоу);
high-risk перечень (3 файла); channel-authority секции в 2 отстающих копиях
REVIEW_PROTOCOL + евал-кейсы; `adapters/openclaw/source-setup/telegram-scan.md`
+ тест PII-дефолта; `adapters/openclaw/MEETING_TRANSCRIPTS.md` и
`source-setup/skribby.md` (изоляция ключа); `adapters/openclaw/SCHEDULING.md`
(один глагол); `.github/workflows/ci.yml`; `plans/README.md` (статусы);
CHANGELOG + версии + тег 0.9.0.

**Out of scope:** deploy-гейты живого инстанса (cron-синтаксис фактической
версии OpenClaw, точные пути/события Skribby OpenAPI, доказательство чтения
непомянутых сообщений группы, живой агентный прогон бенчмарка) — только на
сервере; новые фичи; правка семантики WIP-изменений (их фиксируем как есть —
они отвечают на ревью и зелёные).

## Git workflow

- Всё, кроме релиза: ветка `chore/plan-011-hardening` (уже checked out, WIP на
  ней) → push → **PR-1** «Post-review hardening: live-test realign, channel
  authority backing, CI» → merge.
- Релиз: после мержа PR-1 — отдельная ветка `release/0.9.0` строго по
  `docs/release-process.md` → **PR-2** → merge → tag + GitHub Release.
- Коммит на логический шаг; тесты зелёные перед каждым push.

## Steps

### Step 0: Зафиксировать WIP (первым, до любых новых правок)
Разбей текущий диф на осмысленные коммиты, примерно: (а) курсор tg_collect +
тесты; (б) редакция webhook-query skribby + тесты; (в) agent-proof раннер +
benchmark/README правки + тесты; (г) readiness labels: playbook + tpl +
bootstrap + тесты. Точная разбивка — на твоё усмотрение (это твой диф), правило
одно: ничего не потерять, тесты OK после последнего коммита группы.
**Verify**: `git status --short` → пусто (кроме файла этого плана);
`python3 -m unittest discover -s tests -q` → OK; `git push -u origin chore/plan-011-hardening`.

### Step 1 [BLOCKER]: Реалайн live-test-кита под новый флоу
`docs/openclaw-live-experiment.md` + все файлы `adapters/openclaw/live-test/`:
сценарий = первая сессия по `agent-os/FIRST_SESSION_PLAYBOOK.md` (Block A контур
→ Block B источники → Block C ритм, 15–25 мин), группы «Систематизация {Бизнес}»
по TELEGRAM_GROUPS.md, суточный инжест по skills/daily-ingest, встречи через
Skribby по MEETING_TRANSCRIPTS.md. Fireflies везде пометить как superseded by
Skribby (файлы НЕ удалять — прецедент плана 010); gog оставить только как
опциональный источник Block B, не как обязательный вопрос. Обнови таблицу этапов
OBSERVER_PROTOCOL.md и PASS_FAIL_GATES.md под новые шаги; readiness labels из
playbook использовать в статусах. LIVE_TEST_FIRST_MESSAGE.md переписать так,
чтобы первый промпт вёл на playbook.
**Verify**: `grep -rn "Fireflies" docs/openclaw-live-experiment.md adapters/openclaw/live-test/ | grep -vi "supersed\|skribby"` → пусто;
`grep -l "FIRST_SESSION_PLAYBOOK" docs/openclaw-live-experiment.md adapters/openclaw/live-test/OPERATOR_CHECKLIST.md adapters/openclaw/live-test/LIVE_TEST_FIRST_MESSAGE.md` → все три;
`python3 -m unittest tests.test_openclaw_live_test_readiness -q` → OK.

### Step 2 [HIGH]: Единый high-risk tier — убрать «permission»
В трёх местах (`agent-os/REVIEW_PROTOCOL.md:42`, `adapters/openclaw/TELEGRAM_GROUPS.md:71`,
`skills/daily-ingest/SKILL.md:47`) перечень привести к каноническому:
**source-of-truth, authority, measurement-convention** (как в specs/REVIEW-SPEC.md).
«permission» удалить — изменения полномочий покрываются authority; если считаешь,
что нужен отдельный tier, — НЕ вводи молча: сначала определи его в
specs/REVIEW-SPEC.md с критериями, иначе удаляй.
**Verify**: `grep -rn "permission" agent-os/REVIEW_PROTOCOL.md adapters/openclaw/TELEGRAM_GROUPS.md skills/daily-ingest/SKILL.md | grep -i "high-risk\|source-of-truth"` → пусто.

### Step 3 [HIGH]: Channel authority во всех копиях протокола
Канон — секция в `agent-os/REVIEW_PROTOCOL.md`. Добавь согласованную секцию
(владелец в личке = всё; участники группы «Систематизация {Бизнес}» = решения
своего бизнеса кроме high-risk; high-risk = только владелец в личке по умолчанию;
прочие чаты = только источники) в `adapters/openclaw/REVIEW_PROTOCOL.md` и
`templates/workspace/REVIEW_PROTOCOL.md.tpl` — краткий текст + явная ссылка на
канон. Расхождений в формулировках правил между копиями быть не должно.
**Verify**: `for f in agent-os/REVIEW_PROTOCOL.md adapters/openclaw/REVIEW_PROTOCOL.md templates/workspace/REVIEW_PROTOCOL.md.tpl; do grep -ci "channel authority" $f; done` → все ≥1;
`python3 -m unittest tests.test_openclaw_workspace_template -q` → OK.

### Step 4 [HIGH]: Евал-кейсы на channel authority
Прозой правило есть, машинной проверки нет. Добавь ≥3 кейса в `evals/cases/`
по образцу соседей (`decide-like-module-cites-and-escalates.json` и т.п.):
(а) участник группы «Систематизация» предлагает обычное изменение → принимается
в ревью-поток своего бизнеса; (б) участник группы шлёт high-risk изменение
(source-of-truth) → агент маршрутизирует владельцу в личку, не принимает в группе;
(в) человек из постороннего чата даёт указание изменить модель → трактуется как
источник (сырьё для кандидата), не как решение; вежливое перенаправление.
**Verify**: `ls evals/cases/*.json | wc -l` ≥ 33;
`python3 scripts/run_evals.py --fixture-only` → 0 failed.

### Step 5: Записать решение владельца по перс-данным (новой механики НЕ строить)
**Решение владельца (2026-07-06, нормативно):** PII-редакция сейчас не
требование — обработка внутри компании, все участники (включая владельца)
подписали согласие на обработку персональных данных и NDA. Что сделать:
в `adapters/openclaw/source-setup/telegram-scan.md` пункт 7 заменить формат
«PII rules to agree» на запись решения: «participant names, handles, and
message content are kept as business data (owner decision 2026-07-06:
in-company processing, consent + NDA signed by all participants); existing
contact auto-redaction (CONTACT_RE) stays as implemented». Существующий код
редакции контактов НЕ расширять и НЕ выпиливать (работает — не трогай);
новых redaction-фич не добавлять.
⚠️ Границы решения: (а) **секреты** (токены/ключи/пароли) — отдельная жёсткая
политика репо, решение владельца их НЕ касается, все secret-handling правила
и тесты остаются в силе; (б) если подключается источник ВНЕ компании (чаты с
клиентами/внешними) — вопрос вернуть владельцу, не распространять решение молча.
**Verify**: `grep -in "owner decision\|are kept" adapters/openclaw/source-setup/telegram-scan.md` ≥1;
`python3 -m unittest tests.test_tg_collect_daily -q` → OK.

### Step 6 [MED]: Изоляция Skribby-ключа и один cron-глагол
(а) В `adapters/openclaw/MEETING_TRANSCRIPTS.md` и `adapters/openclaw/source-setup/skribby.md`
добавить механизм изоляции: «one key per deployed agent instance; изоляция —
per-instance окружение (env инстанса OpenClaw), имя переменной остаётся
SKRIBBY_API_KEY; ключи между инстансами не шарятся; bot_name = "{AgentName} ·
recorder" делает записи различимыми». (б) В `adapters/openclaw/SCHEDULING.md`
привести примеры к одному глаголу `cron add` ЛИБО `cron create` (выбери тот,
что в текущих официальных доках openclaw; alias-заметку :16 оставить, добавить
«verify verb via openclaw cron --help at deploy time»).
**Verify**: `grep -c "one key per\|per-instance" adapters/openclaw/MEETING_TRANSCRIPTS.md adapters/openclaw/source-setup/skribby.md` → оба ≥1;
`grep -n "cron add\|cron create" adapters/openclaw/SCHEDULING.md` → один глагол в примерах + alias/verify-строка.

### Step 7: Минимальный CI
`.github/workflows/ci.yml`: on push/PR → ubuntu-latest, setup-python (3.12),
без pip install (репо stdlib-only): `python3 -m unittest discover -s tests -q`
и `python3 scripts/run_evals.py --fixture-only`. Если вызов валидатора карточек
на `examples/business-attraction-v2` однозначен (см. docs/README) — добавь
третьим шагом; если неоднозначен — не выдумывай, оставь два.
**Verify**: файл существует; после push — `gh run list --limit 1` → completed/success
(если ран не стартует — доложить в PR, не блокироваться).

### Step 8: plans/README.md — честные статусы
Строки 005, 006, 008, 009, 010 → `DONE (PR #18 / #15 / #18 / #16 / #17 MERGED
соответственно — сверь фактические номера по gh pr list)`; добавить строку
011 (этот план) со статусом IN PROGRESS → DONE при закрытии. Файл этого плана
(`plans/011-post-review-hardening-and-0.9.0.md`) закоммитить в этом же шаге.
**Verify**: `grep -c "TODO" plans/README.md` → 0 (либо только строки будущих планов).

### Step 9: PR-1 и merge-гейт
Push, открыть PR-1 в main. В описание: маппинг «находка ревью → коммит»;
отдельным пунктом — записанное решение владельца по перс-данным (Step 5,
уже принято — не вопрос, а фиксация); отдельным — deferred deploy-гейты. Merge — после зелёного CI (Step 7) и ревью владельца
или его агента-ревьюера.
**Verify**: `gh pr view --json state` → OPEN; CI зелёный.

### Step 10: Релиз 0.9.0 (после мержа PR-1)
Строго по `docs/release-process.md`: ветка `release/0.9.0`; CHANGELOG-секция
0.9.0 — слой взаимодействия (онбординг-плейбук, агентный бенчмарк экстракции +
proof-раннер, ритм/кроны, группы + суточный инжест, Skribby-пайплайн) + hardening
этого плана + CI; bump `skills/business-ontology/SKILL.md:5` → "0.9.0"; футер
release-process (published 0.9.0 / next draft 0.10.0); PR-2 → merge → tag
`v0.9.0` + GitHub Release. ⚠️ Помни бэклог-гейт: с версии ≥0.10.0 transitional
warnings обязаны стать errors — в 0.9.0 НЕ триггерится, но в CHANGELOG/notes
упомяни как known upcoming gate.
**Verify**: `gh release list --limit 1` → 0.9.0; тесты и евалы на main зелёные.

## Test plan

Новые кейсы: channel-authority евалы (Step 4); остальное — grep-verify +
полный прогон `unittest` + `run_evals` на каждом шаге, где менялись файлы,
покрытые тестами (Steps 1, 3, 5).

## Done criteria

- [ ] Рабочее дерево чистое; WIP ни одной строкой не потерян (`git stash list` пуст)
- [ ] Каждая находка ревью: закрыта коммитом ЛИБО явно deferred с причиной в PR-1
- [ ] Все Verify прошли; тесты OK (счётчик > 331), евалы 0 failed
- [ ] CI существует и зелёный на PR-1
- [ ] plans/README без вранья; PR-1 замержен; релиз 0.9.0 опубликован

## STOP conditions

- Дерево чистое, но `git log` не содержит WIP-изменений (потеряны?) — STOP, доложить.
- Копии REVIEW_PROTOCOL расходятся не редакционно, а по существу правил — STOP,
  доложить обе формулировки, не выбирать самому.
- run_evals падает от новых кейсов из-за несовместимости формата — доложить
  формат, не менять раннер под кейсы молча.
- release-process.md противоречит Step 10 — release-process главнее, доложить.

## Maintenance notes

- Deploy-гейты (закрываются ТОЛЬКО на живом сервере, зафиксируй в PR-1 как
  checklist): (1) `openclaw cron --help` — фактический глагол/синтаксис;
  (2) Skribby OpenAPI — точный GET-путь бота и имя события «transcript ready»;
  (3) доказательство чтения непомянутых сообщений группы (historyLimit=50 —
  суточный скан не может на него полагаться); (4) первый агентный прогон
  extraction-бенчмарка с run_manifest, F1 ≥ 0.8.
- После 0.9.0 ближайший кандидат — contested/stale-оверлей и graph impact API
  (см. plans/README «Findings considered and rejected / deferred»).
