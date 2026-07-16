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
- **Статус**: IN PROGRESS — package, оба workspace и viewer/publication slice
  были завершены на `v0.11.13`; после owner-visible отказа Tailscale URL
  готовится patch `v0.11.14` с отдельным owner-reachability gate. В границах
  всего плана также остаются явное решение владельца о reminder cadence и live
  Telegram acceptance. Продуктовые планы 033–046 не изменяются

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

Final live acceptance (2026-07-15): both agents run package `v0.11.9` at
commit `1aa9bd3e9268a0842ad6711e9b74deb74b4a5f7e`. Their independent Gateway
canaries returned the requested `id`, `version: 0.1.6`, and full `configSchema`
verbatim after a file-read tool call. Their ordinary-chat canaries reduced two
questions to one and included a recommendation and consequence. Both direct
system heartbeats returned `overall_status=ok` with
`external_delivery_allowed=false`. The host still has all 22 pre-existing cron
jobs, including the unchanged Attraction Bitrix job, and has zero managed owner
reminder jobs. No Telegram test message was delivered.

The completion audit then ran the source/raw fixture suite from both installed
release directories. Seventy-one checks passed, while `installed_agent_e2e`
exposed that its temporary source copy retained production
`.package-release.json` metadata. v0.11.10 excludes installation metadata from
fixture source copies and adds an installed-release regression for this path.

Both agents now run `v0.11.10` at
`40f407f32776ccc2ce989e49b4a92cd149945228`. From each installed
`package/current`, 73 source/raw/meeting/review/installed-agent tests passed.
Separate live-mode reports passed against both real workspaces with
`accepted_model_write_attempted=false`. Temporary owner-reply audits also
proved that a blanket acknowledgement answers zero requests, replay creates no
duplicate clarification, an exact reply answers exactly one request, no review
decision is written, and the private reply body is absent from SQLite bytes.

Resident-owned reminder correction (2026-07-15): live inspection showed that
both agents inherited `cron`, `write`, and `exec`, but the package duty skills
were absent from their OpenClaw runtime skill registry. Release `v0.11.11` at
`a5ca87ed92e71cfa7598e627b51ff753980b9746` adds one workspace bridge to
`package/current` and an always-loaded self-service ownership block. The
activation was installed and replayed idempotently on both agents with
`cron_mutated=false`; both now expose `business-ontology-resident` in a fresh
runtime prompt. In independent no-delivery canaries Interlab answered
`Я сам — внешний оператор не нужен`, and Привлечение answered
`Я сам должен спросить владельца, применить ответ и проверить результат`.
Before and after both activations the host definition digest remained
`ec49e2913b3da1605c40775e2349f6baa2ed5f6472d16899c4e2bb224b7880c4`:
22 jobs, zero owner reminders, and the existing Attraction Bitrix job still
enabled at `20 9 * * *`, `Etc/UTC`. No Telegram message was delivered.

Viewer/publication correction (2026-07-15): the live Interlab workspace had no
official published model under `<workspace>/viewer`; instead it contained an
OpenAI Sites scaffold. That path is outside the Resident product boundary and
its public bundle was broken. Release `v0.11.12` makes publication an explicit
runtime capability, denies Sites tools for the Resident agent, writes
content-addressed official bundles, and separates accepted truth from pending
model-change packages. The existing host Tailscale Funnel is the smallest
stable adapter: each agent owns one non-colliding `/models/<agent-id>/` path;
the root route and foreign services stay untouched. A public URL is shareable
only after report/bundle hash, package version, commit, and model revision pass
live verification.

Live v0.11.12 rollout (2026-07-15): PR #35 was merged at
`0d42d266c4abd22dca3ef9affa3168aab91c8893`; the tag workflow passed and the
GitHub Release is the repository's current `Latest`. Both OpenClaw agents run
that exact release, their reversible v0.11.12 migrations passed, both installed
package verifiers report `status=ok`, and both direct heartbeats report
`overall_status=ok` with `external_delivery_allowed=false`. Each agent now has
its own `sites.*` and `codex_apps.sites.*` deny. Their no-delivery Gateway
canaries correctly refused to claim a public viewer while the publication mode
is `workspace-only`.

Private self-service viewer cutover (2026-07-15 UTC / 2026-07-16
Europe/Istanbul): release `v0.11.13` was merged in PR #37 at
`879fecf496f54b5c88116da4516766a2af0c3f67`; the tag workflow passed and the
GitHub Release became `Latest`. The package now fails viewer publication closed
on direct Telegram identities, email addresses, international phone numbers,
private routing fields, secret-like values, and raw working evidence. It runs
one privacy-gated localhost server per agent as a hardened `systemd --user`
service and binds only the agent's non-colliding Tailscale Funnel path. It does
not publish a workspace directory, create a domain/provider account, or grant
host permissions.

Both agents were updated through the same package updater and replayed the
idempotent v0.11.0 managed-behavior migration followed by the v0.11.12 Sites
boundary. Both installed package verifiers return `status=ok` for `v0.11.13`;
Gateway was restarted; owner-chat guard `0.1.7` is loaded; both agents remain on
`openai/gpt-5.6-sol`; and both still deny `sites.*` and
`codex_apps.sites.*`. The silent heartbeat remains every two hours with no
external target. The migration did not invent a reminder schedule.

The live viewers were rebuilt twice: once before cutover and once through the
normal post-configuration publish path. Each report and an independent rescan
have `privacy.status=passed`, each viewer directory retains exactly one current
versioned bundle, and public verification compares the report, bundle, viewer
asset, package commit, and model revision. The current public state is:

- Interlab: `https://ams-1-vm-tcu6.tail871837.ts.net/models/interlab/`, model
  revision `a8882b8`, zero accepted cards, two working packages, eleven working
  changes, one open human request, package `v0.11.13`;
- Привлечение: `https://ams-1-vm-tcu6.tail871837.ts.net/models/attraction/`,
  model revision `9f1717d`, twelve accepted cards, no working packages, package
  `v0.11.13`.

Services `business-ontology-viewer-business-analyst-interlab.service` on
`127.0.0.1:26912` and `business-ontology-viewer-business-analyst.service` on
`127.0.0.1:20972` are enabled and active with `NoNewPrivileges`, `PrivateTmp`,
`ProtectSystem=strict`, and `ProtectHome=read-only`. Funnel still has the
unchanged root proxy to `127.0.0.1:8766` plus only the two `/models/...` paths.
All three public ingress IPv4 addresses returned HTTP 200 from an independent
network path, and an external reader fetched the Interlab report with matching
`v0.11.13`, commit, revision, `publication.status=verified`, and
`privacy.status=passed`. The current Mac network closes direct TLS connections
to those Tailscale ingress addresses (`ERR_CONNECTION_CLOSED`) despite no
configured system proxy. That result does not invalidate the host/hash proof,
but it is still a failed product outcome: the owner cannot use the canonical
link, so the URL must be classified as owner-unreachable and must not be sent
again.

Owner-reachability correction (2026-07-16): the latest Interlab DM proved the
agent sent the same Tailscale URL again after two explicit owner failures and
treated server-side HTTP 200 checks as stronger evidence than the owner's
browser. The patch release candidate separates
`publication.infrastructure_status` from `owner_reachability` and adds a
deterministic `viewer_reachability.py` gate. A new URL can be delivered once;
`unreachable` blocks that exact URL and emits no URL on replay; only explicit
owner confirmation makes it reusable. The state stores no message or
screenshot content. Focused tests, all 580 package tests, 38 fixture evals (240
checks), link validation, compile, and package self-test passed.

The live Interlab workspace now declares the operator-provided static target
`https://interlab.claricont.com/`. Existing Traefik on the owned `claricont.com`
VPS proxies it to the privacy-gated OpenClaw viewer; no new platform, hosting
account, repository, or domain was created. From the owner's Mac network the
ordinary HTTPS index, report, and current versioned bundle return 200 with a
valid certificate, while the original Funnel remains only the server-side
upstream. Explicit owner-open confirmation is still pending.

The actual owner wording regression was executed through Gateway without
delivery: `Ну напиши команду чел` returned one exact copy-ready
`publish_viewer.py` command with the real workspace/model paths, no secret, no
`--skip-public-verification`, and `replayInvalid=false`. A longer synthetic
wording with intervening modifiers did not activate the lexical one-turn
exception and failed closed; therefore broad paraphrase coverage remains a
bounded communication risk, while the owner's observed wording is fixed.

Attraction's durable model support lock was updated through merged PR #7 in
`ontology-attraction`. Interlab's live model support lock is current and its
viewer validates, but the declared private `business-model-interlab` GitHub
repository still contains only its initial README; exporting the existing live
model there remains a separate human-owned model-repository action and was not
silently treated as model acceptance in this rollout.

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
- публикуют официальный viewer из своего workspace через явную host capability;
  не создают OpenAI Site, hosting project, repository или domain;
- показывают принятую модель и рабочие изменения раздельно: рабочий слой всегда
  помечен `not accepted`, а raw evidence/transcript content не публикуется.

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
   Вопрос, применение и postflight выполняет сам resident-агент;
   Codex, installer и host operator не выбирают за него ритм и не создают job.
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
2. Дать агенту package bridge и self-service contract. В своём
   owner-controlled chat агент сам задаёт один вопрос о reminder schedule,
   если действующий contract ещё не был владельцем явно подтверждён.
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

## Пакет 6. Исправить viewer и публикацию без новой платформы

**Владелец файлов**:

- `scripts/publish_viewer.py`, `scripts/build_viewer_bundle.py`;
- `scripts/configure_viewer_publication.py`;
- `viewer/`, `skills/show-model/`, workspace/adapters/spec contracts;
- release workflow/checklist;
- release-specific `scripts/migrate_workspace_v0_11_12.py` и tests.

Контракт:

1. Viewer всегда генерируется в `<workspace>/viewer` и валидирует принятую
   модель до записи.
2. `cards` остаются принятой истиной. Pending package даёт отдельные
   `workingCards` только при наличии schema-valid `candidateCard`; остальные
   changes становятся review items без evidence excerpts/locators.
3. Bundle content-addressed; publish report записывается последним и является
   атомарным указателем на текущую версию.
4. `viewer_publication` имеет только `workspace-only`, `static-url` или
   `tailscale-funnel`. Отсутствующая capability означает text fallback, а не
   разрешение создать внешнюю площадку. Host/hash verification и доступность
   владельцу — разные факты; перед каждой отправкой URL обязателен
   `viewer_reachability.py claim`, а owner-reported failure блокирует повтор
   того же URL.
5. OpenClaw migration с backup/rollback добавляет per-agent deny для `sites.*`
   и `codex_apps.sites.*`, сохраняя существующий tool policy.
6. Сначала live canary Interlab, затем тот же release/migration для
   Привлечения. Tailscale paths добавляются через `--set-path`, без reset root
   route и без изменения чужих jobs/services.
7. Старый Interlab OpenAI Site после успешного cutover переводится в закрытый
   режим; публичная canonical ссылка — только новый verified viewer URL.

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
- viewer report имеет текущий package, `privacy.status=passed`,
  `publication.infrastructure_status=verified` и один текущий versioned
  bundle; public fetch совпадает по hashes/revision, а URL отправляется только
  через owner-reachability gate;
- accepted и working counts проверены независимо, а raw sentinels отсутствуют
  в public index/report/bundle;
- Sites tools отсутствуют из доступного контура агента; существующий Funnel
  root route и Bitrix cron не изменены.

## Rollback

При провале одного агента второй не обновляется. Для затронутого агента:

1. отключить только его package-owned reminder job;
2. вернуть предыдущий package pointer;
3. восстановить behavior files и managed cron definitions из backup;
4. raw и cursors не удалять; использовать сохранённые locators/hashes;
5. restart/re-anchor и повторный read-only proof;
6. не принимать review replies, пока communication/reply guard не доказан.

## Готово, когда

- [x] Исправление существует в versioned package, а не только в двух workspace.
- [x] Один release и одна migration версия стоят у Interlab и Привлечения.
- [ ] Оба агента соблюдают одну коммуникационную модель в live Telegram.
- [x] Blanket reply не способен изменить несколько объектов.
- [x] У каждого агента один private raw root для chats и meetings.
- [x] Heartbeat каждые два часа молчит и обновляет health.
- [ ] Каждый агент сам задал вопрос, получил явный ответ владельца,
  сам применил reminder cadence и доказал actual cron.
- [x] Interlab и Привлечение имеют независимые passed live reports и rollback.
- [x] Viewer исправлен в package/release, сгенерирован и проверен в обоих
  workspace; публичный доступ к старому Interlab OpenAI Site закрыт.
- [x] Два Funnel path привязаны package-owned user services; оба public fetch
  прошли hash/version/revision infrastructure verification.
- [ ] Новый canonical URL Интерлаба прошёл одноразовую отправку через gate и
  владелец явно подтвердил, что ссылка открывается.

## STOP-условия

- Исправление существует только в prompt/workspace одного агента.
- Для Привлечения создаётся другой код или другой communication contract.
- Raw body попадает в package/model/Git/traces/chat или единственная копия
  удаляется до hash reconciliation.
- Heartbeat имеет внешний target или message delivery permission.
- Reminder создаётся до ответа владельца либо изменяет чужие cron jobs.
- «Все ок» закрывает больше одного request или принимает high-risk review.
- Update объявлен завершённым до restart/re-anchor/live smoke.
