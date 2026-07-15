# План 047: Исправить Resident-пакет и раскатить его на Interlab и Привлечение

> **Принцип исполнения**: поведение исправляется один раз в продуктовом
> `business-ontology` package, проверяется как один release и затем одинаковым
> migration path устанавливается двум OpenClaw-агентам. Ручные расходящиеся
> патчи workspace не считаются решением.

## Статус

- **Приоритет**: P0
- **Трудоёмкость**: L
- **Риск**: HIGH
- **Зависит от**: завершённых планов 024 и 027
- **Не зависит от**: продуктовых планов 033–046
- **Статус**: IN PROGRESS

Live canary note (2026-07-15): v0.11.0 exposed an OpenClaw clean-install
ordering failure because the guard schema required `agentIds` before the
migration could configure it. v0.11.1 makes the pre-configuration plugin inert
and refreshes the installed plugin on every workspace activation. Interlab was
stopped before Attraction rollout; no reminder cron was created.

The resumed Interlab canary then exposed a visible OpenClaw tool-failure tail
during a synthetic technical-view probe. v0.11.2 classifies that tail as an
unsafe owner delivery even when technical view is explicitly requested.

A subsequent probe proved that the model still paraphrased successfully read
technical fields. v0.11.3 gives the one-turn technical-view instruction
priority over ordinary-chat translation and requires exact key/value copying.

The v0.11.3 retry then proved that the model treated a private tool result as if
the owner had seen it. v0.11.4 requires the final response itself to contain all
requested fields and forbids an empty "shown" acknowledgement.

The next probe exposed the opposite ambiguity: "private" was treated as a ban
on quoting a successful read. v0.11.5 defines the read result as authoritative
input while keeping it invisible until copied into the final response.

Attraction then reproduced a stochastic paraphrase on the same release that
Interlab passed. v0.11.6 moves completion to the deterministic guard: one
rewrite is allowed, then a technical-view omission fails closed.

The live hook diagnostic proved general rewrites worked but the technical-view
matcher missed OpenClaw's prepended user envelope. v0.11.7 detects the request
inside the latest direct user turn and activates the completion gate there.

The next live canary showed that the finalization history is not an
authoritative carrier for the current request on every harness path. v0.11.8
captures only the technical-view intent at `before_agent_run`, correlates it by
run, and keeps exact-answer enforcement at finalization and delivery.

The v0.11.8 canary exposed the remaining host boundary: OpenClaw skips
`before_agent_finalize` after a completed client tool call. v0.11.9 therefore
adds the exact-rendering instruction at `before_prompt_build` and lets the
delivery hook enforce the correlated intent when finalization is unavailable.

## Результат

Один новый release пакета задаёт и проверяет общее поведение двух установок:

- `business-analyst-interlab` — Бизнес-аналитик Интерлаб;
- `business-analyst` — Бизнес-аналитик Привлечения.

Оба агента:

- говорят по принятой human-коммуникационной модели;
- держат не более одного доставленного владельцу вопроса за раз;
- не превращают «Все ок» или другую общую реплику в несколько решений;
- складывают Telegram-выгрузки и транскрипты в один приватный `raw/` своего
  контура, отдельно от принятой модели и переносимого package;
- каждые два часа молча обновляют состояние системы;
- напоминают о незакрытом только отдельным cron по выбранному владельцем
  расписанию;
- имеют доказуемые package version, workspace migration, cron state, restart и
  live smoke.

## Где находится продуктовая истина

Для этой доработки продуктовый источник поведения — не файлы конкретного
агента, а переносимый package этого репозитория:

```text
specs + agent-os + skills
          ↓
runtime/scripts + OpenClaw adapter + workspace templates + tests
          ↓
versioned release
          ↓
workspace migration
          ↓
Interlab first → Привлечение second
```

`product/` — будущий deployable modular monolith. В нём пока нет semantic
agent, source jobs, review delivery или notification scheduler, которые можно
было бы честно исправить. Его нормативный контракт уже требует брать политику
из package и не создавать второй prompt или approval rule. Поэтому этот план
не добавляет в `product/` заглушки и не меняет планы 033–046. Когда соответствующий
код появится в `product/`, он должен пройти те же contract/eval cases.

## Подтверждённое состояние на 2026-07-15

- OpenClaw: `2026.7.1`; оба агента работают на `openai/gpt-5.6-sol`.
- Interlab установлен через управляемый `package/current` на `v0.10.6`.
- У Привлечения lock указывает на тот же `v0.10.6`, но управляемого
  `package/current` нет. Перед обновлением его install layout нужно привести к
  package contract без потери workspace.
- Оба workspace используют одинаковую старую `COMMUNICATION_POLICY.md`, но
  package update её не обновляет.
- Общий OpenClaw heartbeat уже запускается каждые `2h`, однако это значение
  унаследовано глобально, а запрет внешней доставки не закреплён явно для двух
  аналитиков.
- У Interlab нет agent-owned cron jobs. У Привлечения есть только отдельный
  ежедневный Bitrix drift scan; это не reminder по open requests.
- У Interlab исходники разнесены между `source-exports/` и
  `source-material/meeting-transcripts/`; они исключены из Git. У Привлечения
  единого raw layout пока нет.

## Границы

Меняем только package contracts/runtime/templates/tests, один OpenClaw guard,
существующие collectors, heartbeat/reminder wiring и один release-specific
workspace migration. Не трогаем планы 033–046, accepted model, чужие cron jobs
и placeholder-код в `product/`; не строим новый provider, artifact platform или
retention framework. Владелец отдельно разрешил полный выпуск и live-проверку
обоих установленных агентов; accepted model и чужие cron jobs всё равно вне
границ изменения.

## Пакет 1. Исправить общую коммуникационную модель

**Владелец файлов**:

- `agent-os/COMMUNICATION_POLICY.md`;
- `agent-os/REVIEW_PROTOCOL.md`;
- `skills/meeting-transcript-ingest/SKILL.md`;
- `templates/workspace/COMMUNICATION_POLICY.md.tpl`;
- `templates/workspace/REVIEW_PROTOCOL.md.tpl`;
- `templates/workspace/SOUL.md.tpl`;
- узкий OpenClaw guard под `adapters/openclaw/`;
- `runtime/operational_store.py` только для недостающей reply correlation;
- связанные tests/evals.

Изменения:

1. Убрать противоречие «one to three owner questions». Все найденные вопросы
   сохраняются как `human_request`, но наружу доставляется один: старейший
   blocking/high-risk, затем остальные по очереди.
2. Использовать существующий `messageRef` как границу ответа. Точный reply
   связывается максимум с одним открытым request. Реплика без однозначной связи
   не закрывает ничего и создаёт один уточняющий вопрос.
3. Для review/high-risk простое подтверждение вроде «да», «ок» или «всё хорошо»
   не является действием. Нужны точный объект и действие; actor/channel/revision
   проверяются до записи решения.
4. Добавить один маленький OpenClaw plugin guard, а не новую communication
   platform. OpenClaw `2026.7.1` уже даёт `before_agent_finalize` и
   `message_sending`: первая проверка даёт агенту один шанс исправить ответ,
   вторая отменяет отправку, если в нём всё ещё несколько вопросов, machine ids,
   paths, tool names или raw status codes.
5. Artifact остаётся техническим и полным; guard применяется только к human
   chat. Нельзя независимо сочинять chat и artifact с разным смыслом.

Обязательная регрессия: три открытых вопроса + «Все ок» → ноль закрытых
requests, ноль review decisions, один уточняющий вопрос. Точный reply на один
текущий request → меняется ровно один объект.

## Пакет 2. Сделать единый приватный raw root

**Владелец файлов**:

- `specs/WORKSPACE-SPEC.md`;
- `agent-os/MODEL_STORAGE.md`;
- `agent-os/SOURCE_INTAKE.md`;
- `templates/workspace/runtime-config.example.json.tpl`;
- Telegram exporter/collector;
- meeting transcript capture/service;
- связанные adapter docs и tests.

Контракт:

```text
<raw_source_root>/telegram/<run>/...
<raw_source_root>/meetings/<meeting>/...
```

- Для текущих установок допустим `<private-workspace>/raw/`, потому что это
  операционный репозиторий агента. Каталог обязан быть исключён из Git,
  support bundles, model export, traces и обычного agent context.
- Принятая модель, package repository и redacted workspace artifacts raw body
  не содержат.
- Workspace хранит derived packet/source event, locator, SHA-256 и минимальные
  метаданные обработки.
- Telegram и meeting runtime получают один `raw_source_root` из runtime config;
  самостоятельные hardcoded output roots удаляются.
- Existing Interlab raw переносится после backup и count/hash reconciliation.
  До успешного live proof старые копии не удаляются.
- Для Привлечения создаётся тот же layout; отсутствие старого raw — штатный
  no-op migration.

Не вводить object-store interface, lifecycle engine или новую БД: для двух
текущих VPS-установок достаточно одного filesystem contract, прав доступа,
Git exclusion, hashes и backup.

## Пакет 3. Развести heartbeat и owner reminder

**Общее продуктовое поведение**:

1. Для каждого аналитика явно задать OpenClaw heartbeat:
   `every=2h`, `target=none`, `directPolicy=block`, `isolatedSession=true` и
   `lightContext=true`. Не полагаться на глобальный default.
2. Heartbeat читает короткий `HEARTBEAT.md`, проверяет source/runtime state,
   open requests, package/workspace proof и managed cron health, затем атомарно
   обновляет `agent-state/system-health.json`. Внешней доставки нет.
3. Переименовать digest-терминологию так, чтобы ни skill, ни template не
   называли пользовательскую сводку heartbeat.
4. Напоминание — одна managed cron job на агента. Она запускает детерминированную
   package command, заново читает open requests и health, печатает одну текущую
   сводку либо `NO_REPLY`, если действий нет. Доставку делает OpenClaw cron.
5. Cron создаётся только после ответа владельца о cadence/time, IANA timezone,
   channel и quiet window. Повторная настройка заменяет job того же агента без
   дублей и не затрагивает чужие jobs.
6. Unchanged, но всё ещё открытый request снова появляется в следующем
   выбранном владельцем cadence window. Это не считается пустым повтором.

Перед live rollout остаётся один продуктовый вопрос владельцу для каждого
различающегося расписания. Если расписание одинаковое для обоих агентов, владелец
может одним ответом явно применить его к обоим.

## Пакет 4. Выпустить одно проверяемое обновление

Сделать один release-specific migration script с параметрами `--workspace`,
`--agent-id`, `--dry-run` и `--rollback`. Это не migration framework.

Script:

1. Проверяет поддерживаемую исходную версию/layout.
2. Сохраняет backup и hashes только затрагиваемых behavior files, raw locators
   и managed cron definitions.
3. Показывает diff без credentials, raw bodies и delivery target.
4. Обновляет package-owned policy blocks, сохраняя module identity, model path,
   cursors, open requests, local notes и выбранный interaction contract.
5. Переносит raw с count/hash check.
6. Устанавливает explicit heartbeat config и reconciles только jobs с
   package-owned именами данного agent id.
7. Запускает postflight и пишет migration result в install report.
8. Повторный запуск даёт no-op.

Release gate:

- version/changelog/migration note согласованы;
- fixture old workspace → new workspace проходит для Interlab и Привлечения;
- package self-test и installed-agent E2E зелёные;
- обновление не объявляется завершённым до activation/restart и live proof.

## Пакет 5. Раскатить на два агента

### Interlab — canary

1. Снять package/workspace/raw/cron inventory без private content.
2. Получить ответ владельца о reminder schedule, если действующий contract не
   был им явно подтверждён.
3. Выполнить dry-run, backup, package update и migration.
4. Перезапустить/re-anchor агент и проверить фактически загруженную policy.
5. Выполнить live smoke из раздела ниже.

### Привлечение — second rollout

1. Сначала восстановить управляемый install layout из уже зафиксированного
   `v0.10.6`, не перегенерируя workspace.
2. Повторить тот же release и migration с local config Привлечения.
3. Сохранить существующий Bitrix drift scan; добавить только package-owned
   heartbeat/reminder state.
4. Выполнить тот же live smoke независимо от Interlab.

## Проверка

Package checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_chat_register \
  tests.test_approval_manager \
  tests.test_operational_store \
  tests.test_tg_collect_daily \
  tests.test_tg_mtproto_export \
  tests.test_meeting_transcript_capture \
  tests.test_apply_package_update \
  tests.test_openclaw_workspace_template \
  tests.test_installed_agent_e2e
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_evals.py --fixture-only
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -q
PYTHONDONTWRITEBYTECODE=1 python3 scripts/package_self_test.py --suite-timeout 240
git diff --check
```

Live checks выполняются для каждого agent id:

- package lock, current release и migration result совпадают;
- реальный outbound chat содержит один вопрос, recommendation и consequence,
  без технических маркеров;
- три pending requests + «Все ок» не меняют review/request state;
- точный reply меняет ровно один request;
- Telegram fixture и meeting fixture оказываются под одним `raw/`, а уникальные
  raw sentinels отсутствуют в model, derived workspace, DB, logs и traces;
- два heartbeat run обновляют health snapshot и имеют zero external deliveries;
- reminder cron виден в `openclaw cron list` с нужными agent, schedule, timezone,
  target и next run;
- ручной reminder run доставляет одну свежую сводку, повтор того же run не
  дублирует её, пустая очередь даёт no delivery;
- restart/re-anchor proof показывает, что агент использует новый release.

## Rollback

При провале одного агента второй не обновляется. Для затронутого агента:

1. отключить только его package-owned reminder job;
2. вернуть предыдущий package pointer;
3. восстановить behavior files и managed cron definitions из backup;
4. raw и cursors не удалять; использовать сохранённые locators/hashes;
5. restart/re-anchor и повторный read-only proof;
6. не принимать review replies, пока communication/reply guard не доказан.

## Готово, когда

- [ ] Исправление существует в versioned package, а не только в двух workspace.
- [ ] Один release и одна migration версия стоят у Interlab и Привлечения.
- [ ] Оба агента соблюдают одну коммуникационную модель в live Telegram.
- [ ] Blanket reply не способен изменить несколько объектов.
- [ ] У каждого агента один private raw root для chats и meetings.
- [ ] Heartbeat каждые два часа молчит и обновляет health.
- [ ] Reminder cadence соответствует явному ответу владельца и actual cron.
- [ ] Interlab и Привлечение имеют независимые passed live reports и rollback.

## STOP-условия

- Исправление существует только в prompt/workspace одного агента.
- Для Привлечения создаётся другой код или другой communication contract.
- Raw body попадает в package/model/Git/traces/chat или единственная копия
  удаляется до hash reconciliation.
- Heartbeat имеет внешний target или message delivery permission.
- Reminder создаётся до ответа владельца либо изменяет чужие cron jobs.
- «Все ок» закрывает больше одного request или принимает high-risk review.
- Update объявлен завершённым до restart/re-anchor/live smoke.
