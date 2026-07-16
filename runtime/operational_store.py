#!/usr/bin/env python3
"""SQLite operational store for resident-agent runtime state.

This module persists source-event, model-change-package, review, cursor, run,
and first accepted-state semantic-detail/workflow records. It is local runtime
infrastructure, not a production database adapter, not a connector, and not an
approval gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from runtime.source_event_contract import validate_source_event_contract


PENDING_REVIEW_ACTIONS = {"human-review", "needs-owner"}
NO_REVIEW_ACTIONS = {"no-review-needed"}
TERMINAL_PACKAGE_STATUSES = {
    "approved",
    "rejected",
    "needs-info",
    "superseded",
    "no-op",
    "applied",
    "no-review-needed",
}
OPEN_HUMAN_REQUEST_STATUSES = {"open", "deferred"}
HUMAN_REQUEST_STATUSES = {
    "open",
    "answered",
    "deferred",
    "superseded",
    "cancelled",
}
DECISION_STATUS = {
    "approve": "approved",
    "approved": "approved",
    "approved-with-edits": "approved",
    "reject": "rejected",
    "rejected": "rejected",
    "needs-info": "needs-info",
    "needs_info": "needs-info",
    "supersede": "superseded",
    "superseded": "superseded",
    "record-no-op": "no-op",
    "applied": "applied",
}
# Tables that used to carry a SQLite foreign key to accepted_items(item_id)
# or accepted_workflows(workflow_id). Those ids stopped being unique when
# item/workflow versioning landed, so the foreign keys were dropped and
# integrity is application-enforced (see the per-table schema comments).
# The legacy-layout migration rebuilds any of these tables whose on-disk
# schema still declares the old foreign key.
_APP_INTEGRITY_CHILD_TABLES = (
    "accepted_definitions",
    "accepted_attributes",
    "accepted_criteria",
    "accepted_examples",
    "accepted_data_bindings",
    "accepted_instances",
    "accepted_workflow_participants",
    "accepted_workflow_steps",
    "accepted_workflow_transitions",
    "accepted_workflow_exceptions",
    "accepted_workflow_metrics",
)


class OperationalStore:
    """Small SQLite store for the resident loop and review queue."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def connect(cls, path: Path) -> "OperationalStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(path))

    @classmethod
    def open_readonly(cls, path: Path) -> "OperationalStore":
        return cls(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True))

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "OperationalStore":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    # Single-statement schema source: _ensure_schema and the legacy-layout
    # migration execute these one by one so the whole migration can run in
    # one transaction (executescript would force intermediate commits).
    _SCHEMA_SQL = """
            CREATE TABLE IF NOT EXISTS source_events (
                event_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_items (
                -- One row per item VERSION, item_id stays stable across versions
                -- and the open (current) version is the row with valid_to NULL.
                version_id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                name TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                supersedes TEXT,
                superseded_by TEXT,
                last_verified_at TEXT NOT NULL,
                confidence TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_definitions (
                definition_id TEXT PRIMARY KEY,
                -- item_id integrity is application-enforced: rows are only written
                -- inside record_accepted_item's transaction and accepted item
                -- versions are append-only (no DELETE API), so the old foreign key
                -- with ON DELETE CASCADE was dead code.
                item_id TEXT NOT NULL,
                status TEXT NOT NULL,
                text TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                last_verified_at TEXT NOT NULL,
                confidence TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_attributes (
                attribute_id TEXT PRIMARY KEY,
                -- item_id integrity is application-enforced, written only inside
                -- record_accepted_item's transaction (see accepted_definitions).
                item_id TEXT NOT NULL,
                name TEXT NOT NULL,
                value_type TEXT NOT NULL,
                required INTEGER NOT NULL,
                allowed_values_json TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_criteria (
                criterion_id TEXT PRIMARY KEY,
                -- item_id integrity is application-enforced, written only inside
                -- record_accepted_item's transaction (see accepted_definitions).
                item_id TEXT NOT NULL,
                criterion_type TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                text TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_examples (
                example_id TEXT PRIMARY KEY,
                -- item_id integrity is application-enforced, written only inside
                -- record_accepted_item's transaction (see accepted_definitions).
                item_id TEXT NOT NULL,
                example_type TEXT NOT NULL,
                text TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_workflows (
                -- One row per workflow VERSION, workflow_id stays stable across
                -- versions and the open (current) version has valid_to NULL.
                version_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                start_state_id TEXT NOT NULL,
                end_state_id TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                supersedes TEXT,
                superseded_by TEXT,
                last_verified_at TEXT NOT NULL,
                confidence TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_participants (
                participant_id TEXT PRIMARY KEY,
                -- workflow_id integrity is application-enforced: rows are only
                -- written inside record_accepted_workflow's transaction and
                -- accepted workflow versions are append-only (no DELETE API),
                -- so the old foreign key with ON DELETE CASCADE was dead code.
                workflow_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                role_id TEXT NOT NULL,
                participant_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_steps (
                step_id TEXT PRIMARY KEY,
                -- workflow_id integrity is application-enforced, written only inside
                -- record_accepted_workflow's transaction (see participants table).
                workflow_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                input_ids_json TEXT NOT NULL,
                output_ids_json TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_transitions (
                transition_id TEXT PRIMARY KEY,
                -- workflow_id integrity is application-enforced, written only inside
                -- record_accepted_workflow's transaction (see participants table).
                workflow_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                from_state_id TEXT NOT NULL,
                to_state_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                evidence_rule TEXT NOT NULL,
                authority_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_exceptions (
                exception_id TEXT PRIMARY KEY,
                -- workflow_id integrity is application-enforced, written only inside
                -- record_accepted_workflow's transaction (see participants table).
                workflow_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                condition TEXT NOT NULL,
                handling TEXT NOT NULL,
                severity TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_metrics (
                -- workflow_id integrity is application-enforced, written only inside
                -- record_accepted_workflow's transaction (see participants table).
                workflow_id TEXT NOT NULL,
                metric_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                role TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (workflow_id, metric_id)
            );

            CREATE TABLE IF NOT EXISTS accepted_data_bindings (
                binding_id TEXT PRIMARY KEY,
                -- item_id integrity is application-enforced: record_data_binding
                -- verifies the accepted item exists before writing, and accepted
                -- item versions are append-only (no DELETE API).
                item_id TEXT NOT NULL,
                property_name TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                source_field TEXT NOT NULL,
                value_type TEXT NOT NULL,
                key_field TEXT NOT NULL,
                refresh_policy TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_instances (
                instance_id TEXT PRIMARY KEY,
                -- item_id integrity is application-enforced: record_instance
                -- verifies the accepted item exists before writing, and accepted
                -- item versions are append-only (no DELETE API).
                item_id TEXT NOT NULL,
                label TEXT NOT NULL,
                status TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_instance_relations (
                relation_id TEXT PRIMARY KEY,
                from_instance_id TEXT NOT NULL,
                to_instance_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (from_instance_id) REFERENCES accepted_instances(instance_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (to_instance_id) REFERENCES accepted_instances(instance_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS model_change_packages (
                package_id TEXT PRIMARY KEY,
                module_id TEXT NOT NULL,
                status TEXT NOT NULL,
                risk TEXT NOT NULL,
                review_action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS package_source_events (
                package_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                PRIMARY KEY (package_id, event_id),
                FOREIGN KEY (package_id) REFERENCES model_change_packages(package_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS package_evidence (
                package_id TEXT NOT NULL,
                change_id TEXT NOT NULL,
                source_event_id TEXT NOT NULL,
                locator TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                PRIMARY KEY (package_id, change_id, source_event_id, locator),
                FOREIGN KEY (package_id) REFERENCES model_change_packages(package_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS package_affected_ids (
                package_id TEXT NOT NULL,
                change_id TEXT NOT NULL,
                affected_id TEXT NOT NULL,
                PRIMARY KEY (package_id, change_id, affected_id),
                FOREIGN KEY (package_id) REFERENCES model_change_packages(package_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS human_requests (
                request_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                channel TEXT NOT NULL,
                message_ref TEXT NOT NULL,
                prompt TEXT NOT NULL,
                recommended_answer TEXT NOT NULL,
                blocks_json TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                package_id TEXT,
                asked_at TEXT NOT NULL,
                due_at TEXT,
                answered_at TEXT,
                answer_summary TEXT NOT NULL,
                decision_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (package_id) REFERENCES model_change_packages(package_id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS human_request_context_refs (
                request_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                message_ref TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (channel, message_ref),
                FOREIGN KEY (request_id) REFERENCES human_requests(request_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS human_decisions (
                decision_id TEXT PRIMARY KEY,
                package_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (package_id) REFERENCES model_change_packages(package_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS source_cursors (
                source_id TEXT NOT NULL,
                cursor_key TEXT NOT NULL,
                cursor_value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_id, cursor_key)
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                summary_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_model_change_packages_pending
                ON model_change_packages(status, created_at, package_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_items_kind
                ON accepted_items(kind, status, item_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_items_item
                ON accepted_items(item_id, valid_to);
            CREATE INDEX IF NOT EXISTS idx_accepted_definitions_item
                ON accepted_definitions(item_id, definition_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_attributes_item
                ON accepted_attributes(item_id, name);
            CREATE INDEX IF NOT EXISTS idx_accepted_criteria_item
                ON accepted_criteria(item_id, ordinal, criterion_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_examples_item
                ON accepted_examples(item_id, example_type, example_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_workflows_status
                ON accepted_workflows(status, workflow_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_workflows_workflow
                ON accepted_workflows(workflow_id, valid_to);
            CREATE INDEX IF NOT EXISTS idx_accepted_workflow_participants_workflow
                ON accepted_workflow_participants(workflow_id, sequence, participant_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_workflow_steps_workflow
                ON accepted_workflow_steps(workflow_id, ordinal, step_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_workflow_transitions_workflow
                ON accepted_workflow_transitions(workflow_id, sequence, transition_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_workflow_exceptions_workflow
                ON accepted_workflow_exceptions(workflow_id, sequence, exception_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_workflow_metrics_workflow
                ON accepted_workflow_metrics(workflow_id, sequence, metric_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_data_bindings_item
                ON accepted_data_bindings(item_id, property_name, binding_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_instances_item
                ON accepted_instances(item_id, status, instance_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_instance_relations_from
                ON accepted_instance_relations(from_instance_id, relation_type, relation_id);
            CREATE INDEX IF NOT EXISTS idx_accepted_instance_relations_to
                ON accepted_instance_relations(to_instance_id, relation_type, relation_id);
            CREATE INDEX IF NOT EXISTS idx_human_requests_status
                ON human_requests(status, due_at, asked_at, request_id);
            CREATE INDEX IF NOT EXISTS idx_human_requests_owner_kind
                ON human_requests(owner, kind, status, due_at, request_id);
            CREATE INDEX IF NOT EXISTS idx_human_requests_message_ref
                ON human_requests(channel, message_ref);
            CREATE INDEX IF NOT EXISTS idx_human_requests_package
                ON human_requests(package_id, status, request_id);
            CREATE INDEX IF NOT EXISTS idx_human_request_context_refs_request
                ON human_request_context_refs(request_id, channel, message_ref);
            CREATE INDEX IF NOT EXISTS idx_source_cursors_source
                ON source_cursors(source_id, cursor_key);
            """

    def initialize(self) -> None:
        """Create missing tables and indexes, then migrate legacy layouts."""

        self._ensure_schema()
        self._migrate_legacy_schema()
        self._migrate_legacy_review_questions()

    def _schema_statements(self) -> list[str]:
        return [
            statement.strip()
            for statement in self._SCHEMA_SQL.split(";")
            if statement.strip()
        ]

    def _ensure_schema(self) -> None:
        for statement in self._schema_statements():
            self._connection.execute(statement)
        self._connection.commit()

    def _migrate_legacy_schema(self) -> None:
        """Rebuild pre-versioning tables into the versioned layout in place.

        Legacy layouts keyed accepted_items and accepted_workflows by their
        stable id, so a second version of the same id was impossible, and
        child tables carried SQLite foreign keys to those ids. The rebuild
        copies every row into the new layout (the single legacy row becomes
        version "<id>#v1" with valid_to preserved) and recreates child
        tables without the foreign-key clauses. Runs in one transaction
        with SQLite foreign keys off and is a no-op once migrated.
        """

        parents = [
            (table, id_column)
            for table, id_column in (
                ("accepted_items", "item_id"),
                ("accepted_workflows", "workflow_id"),
            )
            if "version_id" not in self._table_columns(table)
        ]
        children = [
            table
            for table in _APP_INTEGRITY_CHILD_TABLES
            if self._declares_legacy_parent_fk(table)
        ]
        if not parents and not children:
            return

        rebuilt = [table for table, _ in parents] + children
        self._connection.commit()
        # Both pragmas are per-connection and must be set outside a
        # transaction: foreign_keys=OFF so dropping legacy parents cannot
        # cascade into child data, legacy_alter_table=ON so renaming a
        # table aside does not rewrite other tables' references to it.
        self._connection.execute("PRAGMA foreign_keys = OFF")
        self._connection.execute("PRAGMA legacy_alter_table = ON")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                for table in rebuilt:
                    self._connection.execute(
                        f"ALTER TABLE {table} RENAME TO {table}__legacy"
                    )
                for statement in self._schema_statements():
                    self._connection.execute(statement)
                for table, id_column in parents:
                    columns = self._table_columns(table)
                    select_exprs = ", ".join(
                        f"{id_column} || '#v1'"
                        if column == "version_id"
                        else "NULL"
                        if column in ("supersedes", "superseded_by")
                        else column
                        for column in columns
                    )
                    self._connection.execute(
                        f"INSERT INTO {table} ({', '.join(columns)}) "
                        f"SELECT {select_exprs} FROM {table}__legacy"
                    )
                for table in children:
                    columns = ", ".join(self._table_columns(table))
                    self._connection.execute(
                        f"INSERT INTO {table} ({columns}) "
                        f"SELECT {columns} FROM {table}__legacy"
                    )
                for table in rebuilt:
                    self._connection.execute(f"DROP TABLE {table}__legacy")
                # Renamed legacy tables kept the original index names until
                # the drop above released them, re-run the schema statements
                # to restore those indexes on the rebuilt tables.
                for statement in self._schema_statements():
                    self._connection.execute(statement)
                violations = self._connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                if violations:
                    raise ValueError(
                        "legacy schema migration broke referential integrity: "
                        f"{len(violations)} violation(s)"
                    )
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()
        finally:
            self._connection.execute("PRAGMA legacy_alter_table = OFF")
            self._connection.execute("PRAGMA foreign_keys = ON")

    def _table_columns(self, table: str) -> list[str]:
        return [
            str(row["name"])
            for row in self._connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        ]

    def _declares_legacy_parent_fk(self, table: str) -> bool:
        row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if row is None or row["sql"] is None:
            return False
        sql = str(row["sql"])
        return (
            "REFERENCES accepted_items" in sql
            or "REFERENCES accepted_workflows" in sql
        )

    def _table_exists(self, table: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _migrate_legacy_review_questions(self) -> None:
        if not self._table_exists("review_questions"):
            return
        rows = self._connection.execute(
            """
            SELECT question_id, package_id, status, prompt, recommendation,
                   created_at, updated_at
              FROM review_questions
             ORDER BY created_at ASC, question_id ASC
            """
        ).fetchall()
        with self._connection:
            for row in rows:
                status = "answered" if str(row["status"]) in {"resolved", "answered"} else "open"
                asked_at = str(row["created_at"])
                request = {
                    "requestId": f"hreq-{row['question_id']}",
                    "kind": "review",
                    "status": status,
                    "owner": "unknown",
                    "channel": "unknown",
                    "messageRef": "",
                    "prompt": str(row["prompt"]),
                    "recommendedAnswer": str(row["recommendation"]),
                    "blocks": [f"package:{row['package_id']}"],
                    "sourceRef": "",
                    "packageId": str(row["package_id"]),
                    "askedAt": asked_at,
                    "dueAt": "",
                    "answeredAt": str(row["updated_at"]) if status == "answered" else "",
                    "answerSummary": "",
                    "decisionId": None,
                }
                self._insert_human_request(request, now=str(row["updated_at"]))
            self._connection.execute("DROP TABLE review_questions")

    def record_accepted_item(self, item: dict[str, object]) -> str:
        """Persist one accepted model item version and its semantic details.

        Superseded state is linked, never overwritten: when an open version
        (valid_to IS NULL) of item_id already exists and the new payload
        differs, the open version is closed (valid_to set, superseded_by
        pointing at the new version_id) and the new payload is inserted as
        a fresh row whose supersedes points back at the closed version.
        Re-recording a payload identical to the open version is a no-op so
        replayed resident loops do not create duplicate versions.
        """

        item_id = _required_any_str(item, "id", "item_id")
        kind = _required_str(item, "kind")
        status = _required_str(item, "status")
        name = _optional_any_str(item, "name", "title") or item_id
        source_id = _required_str(item, "source_id")
        evidence_id = _required_str(item, "evidence_id")
        decision_id = _required_str(item, "decision_id")
        valid_from = _required_str(item, "valid_from")
        valid_to = _optional_any_str(item, "valid_to")
        last_verified_at = _required_str(item, "last_verified_at")
        confidence = _required_str(item, "confidence")
        payload_json = _json_dumps(item)
        now = _now()

        with self._connection:
            open_version = self._connection.execute(
                """
                SELECT version_id, payload_json
                  FROM accepted_items
                 WHERE item_id = ? AND valid_to IS NULL
                 ORDER BY rowid DESC
                 LIMIT 1
                """,
                (item_id,),
            ).fetchone()
            if open_version is not None and str(open_version["payload_json"]) == payload_json:
                return item_id
            version_id = self._next_version_id("accepted_items", "item_id", item_id)
            supersedes = None
            if open_version is not None:
                supersedes = str(open_version["version_id"])
                self._connection.execute(
                    """
                    UPDATE accepted_items
                       SET valid_to = ?,
                           superseded_by = ?,
                           updated_at = ?
                     WHERE version_id = ?
                    """,
                    (now, version_id, now, supersedes),
                )
            self._connection.execute(
                """
                INSERT INTO accepted_items (
                    version_id, item_id, kind, status, name, source_id,
                    evidence_id, decision_id, valid_from, valid_to,
                    supersedes, superseded_by, last_verified_at, confidence,
                    payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    item_id,
                    kind,
                    status,
                    name,
                    source_id,
                    evidence_id,
                    decision_id,
                    valid_from,
                    valid_to,
                    supersedes,
                    None,
                    last_verified_at,
                    confidence,
                    payload_json,
                    now,
                    now,
                ),
            )
            for table in [
                "accepted_definitions",
                "accepted_attributes",
                "accepted_criteria",
                "accepted_examples",
            ]:
                self._connection.execute(f"DELETE FROM {table} WHERE item_id = ?", (item_id,))
            for definition in _mapping_list(item.get("definitions")):
                self._record_definition(item_id, definition, now)
            for attribute in _mapping_list(item.get("attributes")):
                self._record_attribute(item_id, attribute, now)
            for criterion in _mapping_list(item.get("criteria")):
                self._record_criterion(item_id, criterion, now)
            for example in _mapping_list(item.get("examples")):
                self._record_example(item_id, example, now)
        return item_id

    def _next_version_id(self, table: str, id_column: str, id_value: str) -> str:
        row = self._connection.execute(
            f"SELECT COUNT(*) AS count FROM {table} WHERE {id_column} = ?",
            (id_value,),
        ).fetchone()
        return f"{id_value}#v{int(row['count']) + 1}"

    def _accepted_item_exists(self, item_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM accepted_items WHERE item_id = ? LIMIT 1",
            (item_id,),
        ).fetchone()
        return row is not None

    def get_accepted_item(self, item_id: str) -> dict[str, object] | None:
        """Return the current (open, valid_to IS NULL) version of one item."""

        row = self._connection.execute(
            """
            SELECT payload_json
              FROM accepted_items
             WHERE item_id = ? AND valid_to IS NULL
             ORDER BY rowid DESC
             LIMIT 1
            """,
            (item_id,),
        ).fetchone()
        if row is None:
            return None
        item = _json_loads(str(row["payload_json"]))
        item["definitions"] = [
            _definition_row(row)
            for row in self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_definitions
                 WHERE item_id = ?
                 ORDER BY definition_id ASC
                """,
                (item_id,),
            ).fetchall()
        ]
        item["attributes"] = [
            _attribute_row(row)
            for row in self._connection.execute(
                """
                SELECT payload_json, allowed_values_json
                  FROM accepted_attributes
                 WHERE item_id = ?
                 ORDER BY name ASC, attribute_id ASC
                """,
                (item_id,),
            ).fetchall()
        ]
        item["criteria"] = [
            _json_loads(str(row["payload_json"]))
            for row in self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_criteria
                 WHERE item_id = ?
                 ORDER BY ordinal ASC, criterion_id ASC
                """,
                (item_id,),
            ).fetchall()
        ]
        item["examples"] = [
            _json_loads(str(row["payload_json"]))
            for row in self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_examples
                 WHERE item_id = ?
                 ORDER BY example_type ASC, example_id ASC
                """,
                (item_id,),
            ).fetchall()
        ]
        return item

    def get_item_history(self, item_id: str) -> list[dict[str, object]]:
        """Return every stored version of one accepted item, oldest first.

        Each entry is the recorded payload with the version columns
        (version_id, valid_to, supersedes, superseded_by) overlaid on top,
        so closed versions expose when and by which version they were
        superseded. Semantic-detail children (definitions, attributes,
        criteria, examples) are keyed by the stable item_id rather than by
        version: they always describe the current version and are rewritten
        on each accepted write, so history entries carry no children and
        child history is out of scope here.
        """

        rows = self._connection.execute(
            """
            SELECT payload_json, version_id, valid_to, supersedes, superseded_by
              FROM accepted_items
             WHERE item_id = ?
             ORDER BY rowid ASC
            """,
            (item_id,),
        ).fetchall()
        return [_version_entry(row) for row in rows]

    def list_accepted_items(self, *, kind: str | None = None) -> list[dict[str, object]]:
        if kind:
            rows = self._connection.execute(
                """
                SELECT item_id
                  FROM accepted_items
                 WHERE kind = ? AND valid_to IS NULL
                 ORDER BY kind ASC, item_id ASC
                """,
                (kind,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT item_id
                  FROM accepted_items
                 WHERE valid_to IS NULL
                 ORDER BY kind ASC, item_id ASC
                """
            ).fetchall()
        return [
            item
            for item_id in [str(row["item_id"]) for row in rows]
            if (item := self.get_accepted_item(item_id)) is not None
        ]

    def _record_definition(
        self, item_id: str, definition: dict[str, object], timestamp: str
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO accepted_definitions (
                definition_id, item_id, status, text, source_id, evidence_id,
                decision_id, valid_from, valid_to, last_verified_at, confidence,
                payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(definition, "definition_id"),
                item_id,
                _required_str(definition, "status"),
                _required_str(definition, "text"),
                _required_str(definition, "source_id"),
                _required_str(definition, "evidence_id"),
                _required_str(definition, "decision_id"),
                _required_str(definition, "valid_from"),
                _optional_any_str(definition, "valid_to"),
                _required_str(definition, "last_verified_at"),
                _required_str(definition, "confidence"),
                _json_dumps({**definition, "item_id": item_id}),
                timestamp,
                timestamp,
            ),
        )

    def _record_attribute(
        self, item_id: str, attribute: dict[str, object], timestamp: str
    ) -> None:
        allowed_values = _string_list(attribute.get("allowed_values"))
        self._connection.execute(
            """
            INSERT INTO accepted_attributes (
                attribute_id, item_id, name, value_type, required,
                allowed_values_json, source_id, evidence_id, decision_id,
                payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(attribute, "attribute_id"),
                item_id,
                _required_str(attribute, "name"),
                _required_str(attribute, "value_type"),
                1 if bool(attribute.get("required")) else 0,
                _json_dumps({"allowed_values": allowed_values}),
                _required_str(attribute, "source_id"),
                _required_str(attribute, "evidence_id"),
                _required_str(attribute, "decision_id"),
                _json_dumps({**attribute, "item_id": item_id, "allowed_values": allowed_values}),
                timestamp,
                timestamp,
            ),
        )

    def _record_criterion(
        self, item_id: str, criterion: dict[str, object], timestamp: str
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO accepted_criteria (
                criterion_id, item_id, criterion_type, ordinal, text,
                source_id, evidence_id, decision_id, payload_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(criterion, "criterion_id"),
                item_id,
                _required_str(criterion, "criterion_type"),
                _required_int(criterion, "ordinal"),
                _required_str(criterion, "text"),
                _required_str(criterion, "source_id"),
                _required_str(criterion, "evidence_id"),
                _required_str(criterion, "decision_id"),
                _json_dumps({**criterion, "item_id": item_id}),
                timestamp,
                timestamp,
            ),
        )

    def _record_example(
        self, item_id: str, example: dict[str, object], timestamp: str
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO accepted_examples (
                example_id, item_id, example_type, text, source_id,
                evidence_id, decision_id, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(example, "example_id"),
                item_id,
                _required_str(example, "example_type"),
                _required_str(example, "text"),
                _required_str(example, "source_id"),
                _required_str(example, "evidence_id"),
                _required_str(example, "decision_id"),
                _json_dumps({**example, "item_id": item_id}),
                timestamp,
                timestamp,
            ),
        )

    def record_accepted_workflow(self, workflow: dict[str, object]) -> str:
        """Persist one accepted workflow version and its structured children.

        Versioning mirrors record_accepted_item: an open version whose
        payload differs is closed and linked (superseded_by / supersedes)
        instead of being overwritten, and re-recording an identical payload
        is a no-op. Children stay keyed by the stable workflow_id and always
        describe the current version (see get_workflow_history).
        """

        workflow_id = _required_str(workflow, "workflow_id")
        name = _required_str(workflow, "name")
        status = _required_str(workflow, "status")
        owner = _required_str(workflow, "owner")
        source_id = _required_str(workflow, "source_id")
        evidence_id = _required_str(workflow, "evidence_id")
        decision_id = _required_str(workflow, "decision_id")
        start_state_id = _required_str(workflow, "start_state_id")
        end_state_id = _required_str(workflow, "end_state_id")
        valid_from = _required_str(workflow, "valid_from")
        valid_to = _optional_any_str(workflow, "valid_to")
        last_verified_at = _required_str(workflow, "last_verified_at")
        confidence = _required_str(workflow, "confidence")
        payload_json = _json_dumps(workflow)
        now = _now()

        with self._connection:
            open_version = self._connection.execute(
                """
                SELECT version_id, payload_json
                  FROM accepted_workflows
                 WHERE workflow_id = ? AND valid_to IS NULL
                 ORDER BY rowid DESC
                 LIMIT 1
                """,
                (workflow_id,),
            ).fetchone()
            if open_version is not None and str(open_version["payload_json"]) == payload_json:
                return workflow_id
            version_id = self._next_version_id(
                "accepted_workflows", "workflow_id", workflow_id
            )
            supersedes = None
            if open_version is not None:
                supersedes = str(open_version["version_id"])
                self._connection.execute(
                    """
                    UPDATE accepted_workflows
                       SET valid_to = ?,
                           superseded_by = ?,
                           updated_at = ?
                     WHERE version_id = ?
                    """,
                    (now, version_id, now, supersedes),
                )
            self._connection.execute(
                """
                INSERT INTO accepted_workflows (
                    version_id, workflow_id, name, status, owner, source_id,
                    evidence_id, decision_id, start_state_id, end_state_id,
                    valid_from, valid_to, supersedes, superseded_by,
                    last_verified_at, confidence, payload_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    workflow_id,
                    name,
                    status,
                    owner,
                    source_id,
                    evidence_id,
                    decision_id,
                    start_state_id,
                    end_state_id,
                    valid_from,
                    valid_to,
                    supersedes,
                    None,
                    last_verified_at,
                    confidence,
                    payload_json,
                    now,
                    now,
                ),
            )
            for table in [
                "accepted_workflow_participants",
                "accepted_workflow_steps",
                "accepted_workflow_transitions",
                "accepted_workflow_exceptions",
                "accepted_workflow_metrics",
            ]:
                self._connection.execute(f"DELETE FROM {table} WHERE workflow_id = ?", (workflow_id,))
            for sequence, participant in enumerate(_mapping_list(workflow.get("participants")), 1):
                self._record_workflow_participant(workflow_id, sequence, participant, now)
            for step in _mapping_list(workflow.get("steps")):
                self._record_workflow_step(workflow_id, step, now)
            for sequence, transition in enumerate(_mapping_list(workflow.get("transitions")), 1):
                self._record_workflow_transition(workflow_id, sequence, transition, now)
            for sequence, exception in enumerate(_mapping_list(workflow.get("exceptions")), 1):
                self._record_workflow_exception(workflow_id, sequence, exception, now)
            for sequence, metric in enumerate(_mapping_list(workflow.get("metrics")), 1):
                self._record_workflow_metric(workflow_id, sequence, metric, now)
        return workflow_id

    def get_accepted_workflow(self, workflow_id: str) -> dict[str, object] | None:
        """Return the current (open, valid_to IS NULL) workflow version."""

        row = self._connection.execute(
            """
            SELECT payload_json
              FROM accepted_workflows
             WHERE workflow_id = ? AND valid_to IS NULL
             ORDER BY rowid DESC
             LIMIT 1
            """,
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        workflow = _json_loads(str(row["payload_json"]))
        workflow["participants"] = [
            _json_loads(str(row["payload_json"]))
            for row in self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_workflow_participants
                 WHERE workflow_id = ?
                 ORDER BY sequence ASC, participant_id ASC
                """,
                (workflow_id,),
            ).fetchall()
        ]
        workflow["steps"] = [
            _workflow_step_row(row)
            for row in self._connection.execute(
                """
                SELECT payload_json, input_ids_json, output_ids_json
                  FROM accepted_workflow_steps
                 WHERE workflow_id = ?
                 ORDER BY ordinal ASC, step_id ASC
                """,
                (workflow_id,),
            ).fetchall()
        ]
        workflow["transitions"] = [
            _json_loads(str(row["payload_json"]))
            for row in self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_workflow_transitions
                 WHERE workflow_id = ?
                 ORDER BY sequence ASC, transition_id ASC
                """,
                (workflow_id,),
            ).fetchall()
        ]
        workflow["exceptions"] = [
            _json_loads(str(row["payload_json"]))
            for row in self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_workflow_exceptions
                 WHERE workflow_id = ?
                 ORDER BY sequence ASC, exception_id ASC
                """,
                (workflow_id,),
            ).fetchall()
        ]
        workflow["metrics"] = [
            _json_loads(str(row["payload_json"]))
            for row in self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_workflow_metrics
                 WHERE workflow_id = ?
                 ORDER BY sequence ASC, metric_id ASC
                """,
                (workflow_id,),
            ).fetchall()
        ]
        return workflow

    def get_workflow_history(self, workflow_id: str) -> list[dict[str, object]]:
        """Return every stored version of one workflow, oldest first.

        Entries mirror get_item_history: the recorded payload with
        version_id, valid_to, supersedes, and superseded_by overlaid.
        Structured children (participants, steps, transitions, exceptions,
        metrics) are keyed by the stable workflow_id, describe only the
        current version, and are not carried in history entries.
        """

        rows = self._connection.execute(
            """
            SELECT payload_json, version_id, valid_to, supersedes, superseded_by
              FROM accepted_workflows
             WHERE workflow_id = ?
             ORDER BY rowid ASC
            """,
            (workflow_id,),
        ).fetchall()
        return [_version_entry(row) for row in rows]

    def list_accepted_workflows(self) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """
            SELECT workflow_id
              FROM accepted_workflows
             WHERE valid_to IS NULL
             ORDER BY workflow_id ASC
            """
        ).fetchall()
        return [
            workflow
            for workflow_id in [str(row["workflow_id"]) for row in rows]
            if (workflow := self.get_accepted_workflow(workflow_id)) is not None
        ]

    def record_data_binding(self, binding: dict[str, object]) -> str:
        """Persist one accepted data binding without source values."""

        _reject_raw_fields(binding)
        binding_id = _required_str(binding, "binding_id")
        item_id = _required_str(binding, "item_id")
        property_name = _required_str(binding, "property_name")
        source_id = _required_str(binding, "source_id")
        source_kind = _required_str(binding, "source_kind")
        source_locator = _required_str(binding, "source_locator")
        source_field = _required_str(binding, "source_field")
        value_type = _required_str(binding, "value_type")
        key_field = _required_str(binding, "key_field")
        refresh_policy = _required_str(binding, "refresh_policy")
        # Application-enforced integrity: replaces the dropped SQLite
        # foreign key from accepted_data_bindings to accepted items.
        if not self._accepted_item_exists(item_id):
            raise ValueError(
                f"data binding {binding_id!r} references unknown accepted item {item_id!r}"
            )
        now = _now()
        payload = {
            "binding_id": binding_id,
            "item_id": item_id,
            "property_name": property_name,
            "source_id": source_id,
            "source_kind": source_kind,
            "source_locator": source_locator,
            "source_field": source_field,
            "value_type": value_type,
            "key_field": key_field,
            "refresh_policy": refresh_policy,
        }

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO accepted_data_bindings (
                    binding_id, item_id, property_name, source_id, source_kind,
                    source_locator, source_field, value_type, key_field,
                    refresh_policy, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(binding_id)
                DO UPDATE SET item_id = excluded.item_id,
                              property_name = excluded.property_name,
                              source_id = excluded.source_id,
                              source_kind = excluded.source_kind,
                              source_locator = excluded.source_locator,
                              source_field = excluded.source_field,
                              value_type = excluded.value_type,
                              key_field = excluded.key_field,
                              refresh_policy = excluded.refresh_policy,
                              payload_json = excluded.payload_json,
                              updated_at = excluded.updated_at
                """,
                (
                    binding_id,
                    item_id,
                    property_name,
                    source_id,
                    source_kind,
                    source_locator,
                    source_field,
                    value_type,
                    key_field,
                    refresh_policy,
                    _json_dumps(payload),
                    now,
                    now,
                ),
            )
        return binding_id

    def list_data_bindings(self, *, item_id: str | None = None) -> list[dict[str, object]]:
        if item_id:
            rows = self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_data_bindings
                 WHERE item_id = ?
                 ORDER BY item_id ASC, property_name ASC, binding_id ASC
                """,
                (item_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_data_bindings
                 ORDER BY item_id ASC, property_name ASC, binding_id ASC
                """
            ).fetchall()
        return [_json_loads(str(row["payload_json"])) for row in rows]

    def record_instance(self, instance: dict[str, object]) -> str:
        """Persist one redacted accepted instance."""

        _reject_raw_fields(instance)
        instance_id = _required_str(instance, "instance_id")
        item_id = _required_str(instance, "item_id")
        label = _required_str(instance, "label")
        status = _required_str(instance, "status")
        source_id = _required_str(instance, "source_id")
        evidence_id = _required_str(instance, "evidence_id")
        decision_id = _required_str(instance, "decision_id")
        # Application-enforced integrity: replaces the dropped SQLite
        # foreign key from accepted_instances to accepted items.
        if not self._accepted_item_exists(item_id):
            raise ValueError(
                f"instance {instance_id!r} references unknown accepted item {item_id!r}"
            )
        attributes = _safe_attribute_map(instance.get("attributes"))
        payload = {
            "instance_id": instance_id,
            "item_id": item_id,
            "label": label,
            "status": status,
            "source_id": source_id,
            "evidence_id": evidence_id,
            "decision_id": decision_id,
            "attributes": attributes,
        }
        now = _now()

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO accepted_instances (
                    instance_id, item_id, label, status, source_id, evidence_id,
                    decision_id, attributes_json, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id)
                DO UPDATE SET item_id = excluded.item_id,
                              label = excluded.label,
                              status = excluded.status,
                              source_id = excluded.source_id,
                              evidence_id = excluded.evidence_id,
                              decision_id = excluded.decision_id,
                              attributes_json = excluded.attributes_json,
                              payload_json = excluded.payload_json,
                              updated_at = excluded.updated_at
                """,
                (
                    instance_id,
                    item_id,
                    label,
                    status,
                    source_id,
                    evidence_id,
                    decision_id,
                    _json_dumps(attributes),
                    _json_dumps(payload),
                    now,
                    now,
                ),
            )
        return instance_id

    def list_instances(self, *, item_id: str | None = None) -> list[dict[str, object]]:
        if item_id:
            rows = self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_instances
                 WHERE item_id = ?
                 ORDER BY instance_id ASC
                """,
                (item_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_instances
                 ORDER BY instance_id ASC
                """
            ).fetchall()
        return [_json_loads(str(row["payload_json"])) for row in rows]

    def record_instance_relation(self, relation: dict[str, object]) -> str:
        """Persist one accepted relation between redacted instances."""

        _reject_raw_fields(relation)
        relation_id = _required_str(relation, "relation_id")
        from_instance_id = _required_str(relation, "from_instance_id")
        to_instance_id = _required_str(relation, "to_instance_id")
        relation_type = _required_str(relation, "relation_type")
        source_id = _required_str(relation, "source_id")
        evidence_id = _required_str(relation, "evidence_id")
        decision_id = _required_str(relation, "decision_id")
        payload = {
            "relation_id": relation_id,
            "from_instance_id": from_instance_id,
            "to_instance_id": to_instance_id,
            "relation_type": relation_type,
            "source_id": source_id,
            "evidence_id": evidence_id,
            "decision_id": decision_id,
        }
        now = _now()

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO accepted_instance_relations (
                    relation_id, from_instance_id, to_instance_id, relation_type,
                    source_id, evidence_id, decision_id, payload_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relation_id)
                DO UPDATE SET from_instance_id = excluded.from_instance_id,
                              to_instance_id = excluded.to_instance_id,
                              relation_type = excluded.relation_type,
                              source_id = excluded.source_id,
                              evidence_id = excluded.evidence_id,
                              decision_id = excluded.decision_id,
                              payload_json = excluded.payload_json,
                              updated_at = excluded.updated_at
                """,
                (
                    relation_id,
                    from_instance_id,
                    to_instance_id,
                    relation_type,
                    source_id,
                    evidence_id,
                    decision_id,
                    _json_dumps(payload),
                    now,
                    now,
                ),
            )
        return relation_id

    def list_instance_relations(self) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """
            SELECT payload_json
              FROM accepted_instance_relations
             ORDER BY relation_id ASC
            """
        ).fetchall()
        return [_json_loads(str(row["payload_json"])) for row in rows]

    def query_instance_graph(
        self,
        *,
        root_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        """Return a bounded accepted instance graph neighborhood."""

        limit = max(1, int(limit))
        if root_id:
            ids = {root_id}
            relation_rows = self._connection.execute(
                """
                SELECT payload_json
                  FROM accepted_instance_relations
                 WHERE from_instance_id = ? OR to_instance_id = ?
                 ORDER BY relation_id ASC
                """,
                (root_id, root_id),
            ).fetchall()
            relations = [_json_loads(str(row["payload_json"])) for row in relation_rows]
            for relation in relations:
                ids.add(_required_str(relation, "from_instance_id"))
                ids.add(_required_str(relation, "to_instance_id"))
            placeholders = ",".join("?" for _ in ids)
            instance_rows = self._connection.execute(
                f"""
                SELECT payload_json
                  FROM accepted_instances
                 WHERE instance_id IN ({placeholders})
                 ORDER BY instance_id ASC
                 LIMIT ?
                """,
                (*sorted(ids), limit),
            ).fetchall()
            instances = [_json_loads(str(row["payload_json"])) for row in instance_rows]
            instance_ids = {_required_str(instance, "instance_id") for instance in instances}
            relations = [
                relation
                for relation in relations
                if _required_str(relation, "from_instance_id") in instance_ids
                and _required_str(relation, "to_instance_id") in instance_ids
            ]
            return {
                "instances": instances,
                "relations": relations,
                "truncated": len(ids) > len(instances),
            }

        rows = self._connection.execute(
            """
            SELECT payload_json
              FROM accepted_instances
             ORDER BY instance_id ASC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
        instances = [_json_loads(str(row["payload_json"])) for row in rows]
        instance_ids = {_required_str(instance, "instance_id") for instance in instances}
        relations = [
            relation
            for relation in self.list_instance_relations()
            if _required_str(relation, "from_instance_id") in instance_ids
            and _required_str(relation, "to_instance_id") in instance_ids
        ]
        total = self.table_count("accepted_instances")
        return {
            "instances": instances,
            "relations": relations,
            "truncated": total > len(instances),
        }

    def validate_workflow_refs(
        self,
        workflow: dict[str, object],
        *,
        extra_item_ids: set[str] | None = None,
    ) -> list[str]:
        """Return accepted-item references that the workflow cannot resolve."""

        normalized = _normalize_accepted_workflow_bundle(workflow)
        accepted_ids = set(extra_item_ids or set())
        rows = self._connection.execute("SELECT item_id FROM accepted_items").fetchall()
        accepted_ids.update(str(row["item_id"]) for row in rows)

        missing: list[str] = []
        for label, item_id in _workflow_ref_pairs(normalized):
            if item_id == "unknown":
                continue
            problem = f"{label}={item_id}"
            if item_id not in accepted_ids and problem not in missing:
                missing.append(problem)
        return missing

    def _record_workflow_participant(
        self,
        workflow_id: str,
        sequence: int,
        participant: dict[str, object],
        timestamp: str,
    ) -> None:
        payload = {**participant, "workflow_id": workflow_id}
        self._connection.execute(
            """
            INSERT INTO accepted_workflow_participants (
                participant_id, workflow_id, sequence, role_id,
                participant_type, source_id, evidence_id, decision_id,
                payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(participant, "participant_id"),
                workflow_id,
                sequence,
                _required_str(participant, "role_id"),
                _required_str(participant, "participant_type"),
                _required_str(participant, "source_id"),
                _required_str(participant, "evidence_id"),
                _required_str(participant, "decision_id"),
                _json_dumps(payload),
                timestamp,
                timestamp,
            ),
        )

    def _record_workflow_step(
        self, workflow_id: str, step: dict[str, object], timestamp: str
    ) -> None:
        input_ids = _string_list(step.get("input_ids"))
        output_ids = _string_list(step.get("output_ids"))
        payload = {
            **step,
            "workflow_id": workflow_id,
            "input_ids": input_ids,
            "output_ids": output_ids,
        }
        self._connection.execute(
            """
            INSERT INTO accepted_workflow_steps (
                step_id, workflow_id, ordinal, actor_id, action,
                input_ids_json, output_ids_json, source_id, evidence_id,
                decision_id, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(step, "step_id"),
                workflow_id,
                _required_int(step, "ordinal"),
                _required_str(step, "actor_id"),
                _required_str(step, "action"),
                _json_dumps({"input_ids": input_ids}),
                _json_dumps({"output_ids": output_ids}),
                _required_str(step, "source_id"),
                _required_str(step, "evidence_id"),
                _required_str(step, "decision_id"),
                _json_dumps(payload),
                timestamp,
                timestamp,
            ),
        )

    def _record_workflow_transition(
        self,
        workflow_id: str,
        sequence: int,
        transition: dict[str, object],
        timestamp: str,
    ) -> None:
        payload = {**transition, "workflow_id": workflow_id}
        self._connection.execute(
            """
            INSERT INTO accepted_workflow_transitions (
                transition_id, workflow_id, sequence, from_state_id,
                to_state_id, trigger, evidence_rule, authority_id, source_id,
                evidence_id, decision_id, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(transition, "transition_id"),
                workflow_id,
                sequence,
                _required_str(transition, "from_state_id"),
                _required_str(transition, "to_state_id"),
                _required_str(transition, "trigger"),
                _required_str(transition, "evidence_rule"),
                _required_str(transition, "authority_id"),
                _required_str(transition, "source_id"),
                _required_str(transition, "evidence_id"),
                _required_str(transition, "decision_id"),
                _json_dumps(payload),
                timestamp,
                timestamp,
            ),
        )

    def _record_workflow_exception(
        self,
        workflow_id: str,
        sequence: int,
        exception: dict[str, object],
        timestamp: str,
    ) -> None:
        payload = {**exception, "workflow_id": workflow_id}
        self._connection.execute(
            """
            INSERT INTO accepted_workflow_exceptions (
                exception_id, workflow_id, sequence, condition, handling,
                severity, source_id, evidence_id, decision_id, payload_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_str(exception, "exception_id"),
                workflow_id,
                sequence,
                _required_str(exception, "condition"),
                _required_str(exception, "handling"),
                _required_str(exception, "severity"),
                _required_str(exception, "source_id"),
                _required_str(exception, "evidence_id"),
                _required_str(exception, "decision_id"),
                _json_dumps(payload),
                timestamp,
                timestamp,
            ),
        )

    def _record_workflow_metric(
        self,
        workflow_id: str,
        sequence: int,
        metric: dict[str, object],
        timestamp: str,
    ) -> None:
        payload = {**metric, "workflow_id": workflow_id}
        self._connection.execute(
            """
            INSERT INTO accepted_workflow_metrics (
                workflow_id, metric_id, sequence, role, source_id, evidence_id,
                decision_id, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                _required_str(metric, "metric_id"),
                sequence,
                _required_str(metric, "role"),
                _required_str(metric, "source_id"),
                _required_str(metric, "evidence_id"),
                _required_str(metric, "decision_id"),
                _json_dumps(payload),
                timestamp,
                timestamp,
            ),
        )

    def source_event_seen(self, event_id: str, event_hash: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
              FROM source_events
             WHERE event_id = ? OR hash = ?
             LIMIT 1
            """,
            (event_id, event_hash),
        ).fetchone()
        return row is not None

    def record_source_event(self, event: dict[str, object]) -> str:
        validate_source_event_contract(event)
        event_id = _required_str(event, "eventId")
        event_hash = _required_str(event, "hash")
        existing = self._connection.execute(
            """
            SELECT event_id
              FROM source_events
             WHERE event_id = ? OR hash = ?
             ORDER BY event_id = ? DESC
             LIMIT 1
            """,
            (event_id, event_hash, event_id),
        ).fetchone()
        if existing is not None:
            return str(existing["event_id"])

        self._connection.execute(
            """
            INSERT INTO source_events (
                event_id, source_id, source_kind, observed_at, hash,
                payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                _required_str(event, "sourceId"),
                _required_str(event, "sourceKind"),
                _required_str(event, "observedAt"),
                event_hash,
                _json_dumps(event),
                _now(),
            ),
        )
        self._connection.commit()
        return event_id

    def get_source_event(self, event_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """
            SELECT payload_json
              FROM source_events
             WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        if row is None:
            return None
        return _json_loads(str(row["payload_json"]))

    def record_model_change_package(self, package: dict[str, object]) -> str:
        package_id = _required_str(package, "packageId")
        module_id = _required_str(package, "moduleId")
        review_action = _review_action(package)
        status = _package_status(review_action)
        risk = _package_risk(package)
        payload_json = _json_dumps(package)
        now = _now()

        with self._connection:
            existing = self._connection.execute(
                "SELECT status, payload_json FROM model_change_packages WHERE package_id = ?",
                (package_id,),
            ).fetchone()
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO model_change_packages (
                        package_id, module_id, status, risk, review_action,
                        payload_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (package_id, module_id, status, risk, review_action, payload_json, now, now),
                )
            else:
                stored_status = str(existing["status"])
                stored_payload = str(existing["payload_json"])
                if stored_status in TERMINAL_PACKAGE_STATUSES:
                    if stored_payload != payload_json:
                        raise ValueError(
                            f"cannot rewrite reviewed model change package {package_id}"
                        )
                    if stored_status == "no-review-needed":
                        self._connection.execute(
                            """
                            UPDATE model_change_packages
                               SET status = ?,
                                   updated_at = ?
                             WHERE package_id = ?
                            """,
                            ("no-op", now, package_id),
                        )
                    return package_id
                next_status = status if stored_status == "pending" else stored_status
                self._connection.execute(
                    """
                    UPDATE model_change_packages
                       SET module_id = ?,
                           status = ?,
                           risk = ?,
                           review_action = ?,
                           payload_json = ?,
                           updated_at = ?
                     WHERE package_id = ?
                    """,
                    (module_id, next_status, risk, review_action, payload_json, now, package_id),
                )

            self._connection.execute(
                "DELETE FROM package_source_events WHERE package_id = ?",
                (package_id,),
            )
            self._connection.execute(
                "DELETE FROM package_evidence WHERE package_id = ?",
                (package_id,),
            )
            self._connection.execute(
                "DELETE FROM package_affected_ids WHERE package_id = ?",
                (package_id,),
            )
            for event_id in _string_list(package.get("sourceEventIds")):
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO package_source_events(package_id, event_id)
                    VALUES (?, ?)
                    """,
                    (package_id, event_id),
                )
            for change in _mapping_list(package.get("changes")):
                change_id = _required_str(change, "changeId")
                for evidence in _mapping_list(change.get("evidence")):
                    self._connection.execute(
                        """
                        INSERT OR IGNORE INTO package_evidence (
                            package_id, change_id, source_event_id, locator, excerpt
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            package_id,
                            change_id,
                            _required_str(evidence, "sourceEventId"),
                            _required_str(evidence, "locator"),
                            _required_str(evidence, "excerpt"),
                        ),
                    )
                for affected_id in _string_list(change.get("affectedIds")):
                    self._connection.execute(
                        """
                        INSERT OR IGNORE INTO package_affected_ids (
                            package_id, change_id, affected_id
                        )
                        VALUES (?, ?, ?)
                        """,
                        (package_id, change_id, affected_id),
            )
        return package_id

    def apply_approved_model_change(
        self,
        package: dict[str, object],
        *,
        allow_stale: bool = False,
        current_revision: str | None = None,
    ) -> dict[str, list[str]]:
        """Apply approved accepted-state payloads from a model-change package.

        When current_revision is provided and the package's ontologyRevision
        differs, the package is stale (compiled against an outdated model)
        and the apply is refused unless allow_stale=True. Callers that do
        not pass current_revision keep the pre-detection behavior: no
        staleness check is possible, so none is performed.
        """

        package_id = _required_str(package, "packageId")
        package_status = self._package_status(package_id)
        if package_status != "approved":
            raise ValueError(f"model change package {package_id} is not approved")
        package_revision = str(package.get("ontologyRevision", ""))
        if _package_is_stale(package_revision, current_revision) and not allow_stale:
            raise ValueError(
                f"model change package {package_id} is stale: it was compiled "
                f"against ontology revision {package_revision!r} but the current "
                f"revision is {current_revision!r}; re-compile the package against "
                "the current model or pass allow_stale=True to apply anyway"
            )

        item_records: list[dict[str, object]] = []
        workflow_records: list[dict[str, object]] = []
        for change in _mapping_list(package.get("changes")):
            item = _accepted_item_from_change(change)
            if item is not None:
                item_records.append(item)
            workflow = _accepted_workflow_from_change(change)
            if workflow is not None:
                workflow_records.append(workflow)

        package_item_ids = {_required_any_str(item, "id", "item_id") for item in item_records}
        for workflow in workflow_records:
            missing = self.validate_workflow_refs(workflow, extra_item_ids=package_item_ids)
            if missing:
                raise ValueError("workflow refs do not resolve: " + ", ".join(missing))

        applied_items = [self.record_accepted_item(item) for item in item_records]
        applied_workflows = [self.record_accepted_workflow(workflow) for workflow in workflow_records]

        with self._connection:
            self._connection.execute(
                """
                UPDATE model_change_packages
                   SET status = ?,
                       updated_at = ?
                 WHERE package_id = ?
                """,
                ("applied", _now(), package_id),
            )
        return {"items": applied_items, "workflows": applied_workflows}

    def _package_status(self, package_id: str) -> str:
        row = self._connection.execute(
            """
            SELECT status
              FROM model_change_packages
             WHERE package_id = ?
            """,
            (package_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"model change package {package_id} is not recorded")
        return str(row["status"])

    def list_pending_packages(
        self,
        *,
        limit: int = 50,
        current_revision: str | None = None,
    ) -> list[dict[str, object]]:
        """Return bounded pending-package summaries, oldest first.

        When current_revision is provided, each summary's "stale" field is
        computed against it (True when the package's ontologyRevision is
        present and differs). Without current_revision the field stays
        False, preserving the behavior of callers that cannot know the
        current model revision.
        """

        rows = self._connection.execute(
            """
            SELECT package_id, module_id, status, risk, review_action, created_at, payload_json
              FROM model_change_packages
             WHERE status = 'pending'
             ORDER BY created_at ASC, package_id ASC
             LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [
            _package_summary(row, current_revision=current_revision) for row in rows
        ]

    def get_model_change_package(self, package_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """
            SELECT payload_json
              FROM model_change_packages
             WHERE package_id = ?
            """,
            (package_id,),
        ).fetchone()
        if row is None:
            return None
        return _json_loads(str(row["payload_json"]))

    def count_pending_packages(self) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS count
              FROM model_change_packages
             WHERE status = 'pending'
            """
        ).fetchone()
        return int(row["count"])

    def record_human_decision(self, review_id: str, decision: dict[str, object]) -> str:
        decision_id = review_id
        package_id = _required_any_str(decision, "packageId", "package_id")
        action = _required_any_str(decision, "decision", "action")
        actor = _optional_any_str(decision, "actor", "reviewer") or "unknown"
        reason = _optional_any_str(decision, "reason", "summary") or "unknown"
        decided_at = _optional_any_str(decision, "decidedAt", "decided_at", "timestamp") or _now()
        package_status = DECISION_STATUS.get(action, action)
        payload_json = _json_dumps(decision)

        with self._connection:
            existing = self._connection.execute(
                "SELECT payload_json FROM human_decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_json"]) != payload_json:
                    raise ValueError(f"cannot rewrite human decision {decision_id}")
                return decision_id
            self._connection.execute(
                """
                INSERT INTO human_decisions (
                    decision_id, package_id, actor, decision, reason,
                    decided_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (decision_id, package_id, actor, action, reason, decided_at, payload_json),
            )
            self._connection.execute(
                """
                UPDATE model_change_packages
                   SET status = ?,
                       updated_at = ?
                 WHERE package_id = ?
                """,
                (package_status, _now(), package_id),
            )
        return decision_id

    def record_human_request(self, request: dict[str, object]) -> str:
        request_id = _required_any_str(request, "requestId", "request_id")
        payload_json = _json_dumps(_human_request_payload(request))
        now = _now()
        with self._connection:
            existing = self._connection.execute(
                "SELECT payload_json FROM human_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["payload_json"]) != payload_json:
                    raise ValueError(f"cannot rewrite human request {request_id}")
                return request_id
            self._insert_human_request(request, now=now)
        return request_id

    def _insert_human_request(self, request: dict[str, object], *, now: str) -> None:
        request_id = _required_any_str(request, "requestId", "request_id")
        status = _human_request_status(_optional_any_str(request, "status") or "open")
        kind = _required_str(request, "kind")
        owner = _optional_any_str(request, "owner") or "unknown"
        channel = _optional_any_str(request, "channel") or "unknown"
        message_ref = _optional_any_str(request, "messageRef", "message_ref") or ""
        prompt = _required_str(request, "prompt")
        recommended_answer = _required_any_str(
            request,
            "recommendedAnswer",
            "recommended_answer",
            "recommendation",
        )
        blocks = _string_list(request.get("blocks"))
        source_ref = _optional_any_str(request, "sourceRef", "source_ref") or ""
        package_id = _optional_any_str(request, "packageId", "package_id")
        asked_at = _optional_any_str(request, "askedAt", "asked_at") or now
        due_at = _optional_any_str(request, "dueAt", "due_at")
        answered_at = _optional_any_str(request, "answeredAt", "answered_at")
        answer_summary = _optional_any_str(request, "answerSummary", "answer_summary") or ""
        decision_id = _optional_any_str(request, "decisionId", "decision_id")
        self._connection.execute(
            """
            INSERT INTO human_requests (
                request_id, kind, status, owner, channel, message_ref,
                prompt, recommended_answer, blocks_json, source_ref,
                package_id, asked_at, due_at, answered_at, answer_summary,
                decision_id, payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                kind,
                status,
                owner,
                channel,
                message_ref,
                prompt,
                recommended_answer,
                _json_dumps({"blocks": blocks}),
                source_ref,
                package_id,
                asked_at,
                due_at or None,
                answered_at or None,
                answer_summary,
                decision_id,
                _json_dumps(_human_request_payload(request)),
                now,
                now,
            ),
        )

    def get_human_request(self, request_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """
            SELECT request_id, kind, status, owner, channel, message_ref,
                   prompt, recommended_answer, blocks_json, source_ref,
                   package_id, asked_at, due_at, answered_at, answer_summary,
                   decision_id, created_at, updated_at
              FROM human_requests
             WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return _human_request_row(row)

    def find_human_request_by_message_ref(
        self,
        channel: str,
        message_ref: str,
    ) -> dict[str, object] | None:
        row = self._connection.execute(
            """
            SELECT request_id, kind, status, owner, channel, message_ref,
                   prompt, recommended_answer, blocks_json, source_ref,
                   package_id, asked_at, due_at, answered_at, answer_summary,
                   decision_id, created_at, updated_at
              FROM human_requests
             WHERE channel = ? AND message_ref = ?
             ORDER BY asked_at DESC, request_id DESC
             LIMIT 1
            """,
            (channel, message_ref),
        ).fetchone()
        if row is None:
            return None
        return _human_request_row(row)

    def bind_human_request_message_ref(
        self,
        request_id: str,
        *,
        message_ref: str,
    ) -> str:
        """Replace one provisional delivery ref with the host's actual ref.

        Questions are recorded before delivery, when Telegram has not assigned
        a message id yet. Only an open request whose ref starts with
        ``pending:`` can be bound, and an actual ref can belong to only one
        request across the store.
        """

        actual_ref = message_ref.strip()
        if not actual_ref or actual_ref.startswith("pending:"):
            raise ValueError("actual human request message ref is invalid")
        row = self._connection.execute(
            """
            SELECT status, message_ref, payload_json
              FROM human_requests
             WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"human request {request_id} is not recorded")
        status = str(row["status"])
        current_ref = str(row["message_ref"])
        if current_ref == actual_ref:
            return request_id
        if status not in OPEN_HUMAN_REQUEST_STATUSES:
            raise ValueError(f"cannot bind closed human request {request_id}")
        if not current_ref.startswith("pending:"):
            raise ValueError(f"human request {request_id} has no provisional message ref")
        conflict = self._connection.execute(
            """
            SELECT request_id
              FROM human_requests
             WHERE message_ref = ? AND request_id != ?
             LIMIT 1
            """,
            (actual_ref, request_id),
        ).fetchone()
        if conflict is not None:
            raise ValueError("human request message ref is already bound")
        payload = _json_loads(str(row["payload_json"]))
        payload["messageRef"] = actual_ref
        with self._connection:
            self._connection.execute(
                """
                UPDATE human_requests
                   SET message_ref = ?, payload_json = ?, updated_at = ?
                 WHERE request_id = ?
                """,
                (actual_ref, _json_dumps(payload), _now(), request_id),
            )
        return request_id

    def list_open_human_requests(
        self,
        *,
        limit: int = 50,
        owner: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, object]]:
        clauses = ["status IN ('open', 'deferred')"]
        params: list[object] = []
        if owner:
            clauses.append("owner = ?")
            params.append(owner)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        params.append(max(1, int(limit)))
        rows = self._connection.execute(
            f"""
            SELECT request_id, kind, status, owner, channel, message_ref,
                   prompt, recommended_answer, blocks_json, source_ref,
                   package_id, asked_at, due_at, answered_at, answer_summary,
                   decision_id, created_at, updated_at
              FROM human_requests
             WHERE {' AND '.join(clauses)}
             ORDER BY COALESCE(NULLIF(due_at, ''), asked_at) ASC,
                      asked_at ASC,
                      request_id ASC
             LIMIT ?
            """,
            params,
        ).fetchall()
        return [_human_request_row(row) for row in rows]

    def mark_human_request_answered(
        self,
        request_id: str,
        *,
        answer_summary: str,
        decision_id: str | None = None,
        answered_at: str | None = None,
    ) -> str:
        row = self._connection.execute(
            "SELECT status FROM human_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"human request {request_id} is not recorded")
        timestamp = answered_at or _now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE human_requests
                   SET status = 'answered',
                       answered_at = ?,
                       answer_summary = ?,
                       decision_id = COALESCE(?, decision_id),
                       updated_at = ?
                 WHERE request_id = ?
                """,
                (timestamp, answer_summary, decision_id, _now(), request_id),
            )
        return request_id

    def record_human_request_context_ref(
        self,
        request_id: str,
        *,
        channel: str,
        message_ref: str,
        source: str,
    ) -> str:
        """Bind a safe alternate message reference to one open request."""

        normalized_channel = channel.strip()
        normalized_ref = message_ref.strip()
        normalized_source = source.strip()
        if not normalized_channel or not normalized_ref or not normalized_source:
            raise ValueError("human request context ref fields must be non-empty")
        request = self._connection.execute(
            "SELECT status FROM human_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if request is None:
            raise ValueError(f"human request {request_id} is not recorded")
        if str(request["status"]) not in OPEN_HUMAN_REQUEST_STATUSES:
            raise ValueError(f"cannot bind context to closed human request {request_id}")
        existing = self._connection.execute(
            """
            SELECT request_id, source
              FROM human_request_context_refs
             WHERE channel = ? AND message_ref = ?
            """,
            (normalized_channel, normalized_ref),
        ).fetchone()
        if existing is not None:
            if (
                str(existing["request_id"]) != request_id
                or str(existing["source"]) != normalized_source
            ):
                raise ValueError("human request context ref is already bound differently")
            return request_id
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO human_request_context_refs (
                    request_id, channel, message_ref, source, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    normalized_channel,
                    normalized_ref,
                    normalized_source,
                    _now(),
                ),
            )
        return request_id

    def list_human_request_context_refs(
        self,
        *,
        request_id: str | None = None,
        limit: int = 10_000,
    ) -> list[dict[str, object]]:
        clauses: list[str] = []
        params: list[object] = []
        if request_id:
            clauses.append("request_id = ?")
            params.append(request_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, int(limit)))
        rows = self._connection.execute(
            f"""
            SELECT request_id, channel, message_ref, source, created_at
              FROM human_request_context_refs
              {where}
             ORDER BY created_at ASC, channel ASC, message_ref ASC
             LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            {
                "requestId": str(row["request_id"]),
                "channel": str(row["channel"]),
                "messageRef": str(row["message_ref"]),
                "source": str(row["source"]),
                "createdAt": str(row["created_at"]),
            }
            for row in rows
        ]

    def defer_human_request(
        self,
        request_id: str,
        *,
        due_at: str | None = None,
    ) -> str:
        row = self._connection.execute(
            "SELECT status FROM human_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"human request {request_id} is not recorded")
        if str(row["status"]) not in OPEN_HUMAN_REQUEST_STATUSES:
            raise ValueError(f"cannot defer closed human request {request_id}")
        with self._connection:
            self._connection.execute(
                """
                UPDATE human_requests
                   SET status = 'deferred',
                       due_at = COALESCE(?, due_at),
                       updated_at = ?
                 WHERE request_id = ?
                """,
                (due_at, _now(), request_id),
            )
        return request_id

    def cancel_human_request(
        self,
        request_id: str,
        *,
        reason: str,
    ) -> str:
        """Close one still-open request without treating it as an answer."""

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("human request cancellation reason is required")
        row = self._connection.execute(
            "SELECT status FROM human_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"human request {request_id} is not recorded")
        if str(row["status"]) not in OPEN_HUMAN_REQUEST_STATUSES:
            raise ValueError(f"cannot cancel closed human request {request_id}")
        with self._connection:
            self._connection.execute(
                """
                UPDATE human_requests
                   SET status = 'cancelled',
                       answer_summary = ?,
                       updated_at = ?
                 WHERE request_id = ?
                """,
                (normalized_reason, _now(), request_id),
            )
        return request_id

    def upsert_source_cursor(
        self,
        source_id: str,
        cursor_key: str,
        cursor_value: str,
        *,
        updated_at: str | None = None,
    ) -> str:
        timestamp = updated_at or _now()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO source_cursors(source_id, cursor_key, cursor_value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id, cursor_key)
                DO UPDATE SET cursor_value = excluded.cursor_value,
                              updated_at = excluded.updated_at
                """,
                (source_id, cursor_key, cursor_value, timestamp),
            )
        return cursor_value

    def get_source_cursor(self, source_id: str, cursor_key: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """
            SELECT source_id, cursor_key, cursor_value, updated_at
              FROM source_cursors
             WHERE source_id = ? AND cursor_key = ?
            """,
            (source_id, cursor_key),
        ).fetchone()
        if row is None:
            return None
        return _row_dict(row)

    def record_run(self, run: dict[str, object]) -> str:
        run_id = _required_any_str(run, "runId", "run_id")
        status = _required_str(run, "status")
        started_at = _optional_any_str(run, "startedAt", "started_at") or _now()
        finished_at = _optional_any_str(run, "finishedAt", "finished_at")
        summary = run.get("summary", run)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO runs(run_id, status, started_at, finished_at, summary_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id)
                DO UPDATE SET status = excluded.status,
                              started_at = excluded.started_at,
                              finished_at = excluded.finished_at,
                              summary_json = excluded.summary_json
                """,
                (run_id, status, started_at, finished_at, _json_dumps(summary)),
            )
        return run_id

    def table_count(self, table: str) -> int:
        if table not in {
            "accepted_items",
            "accepted_definitions",
            "accepted_attributes",
            "accepted_criteria",
            "accepted_examples",
            "accepted_workflows",
            "accepted_workflow_participants",
            "accepted_workflow_steps",
            "accepted_workflow_transitions",
            "accepted_workflow_exceptions",
            "accepted_workflow_metrics",
            "accepted_data_bindings",
            "accepted_instances",
            "accepted_instance_relations",
            "source_events",
            "model_change_packages",
            "package_source_events",
            "package_evidence",
            "package_affected_ids",
            "human_requests",
            "human_request_context_refs",
            "human_decisions",
            "source_cursors",
            "runs",
        }:
            raise ValueError(f"unknown operational store table: {table}")
        row = self._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        return int(row["count"])


def _package_status(review_action: str) -> str:
    if review_action in PENDING_REVIEW_ACTIONS:
        return "pending"
    if review_action in NO_REVIEW_ACTIONS:
        return "no-op"
    return "pending"


def _package_risk(package: dict[str, object]) -> str:
    rank = {"low": 0, "medium": 1, "high": 2}
    highest = "low"
    for change in _mapping_list(package.get("changes")):
        risk = change.get("risk")
        if isinstance(risk, str) and rank.get(risk, -1) > rank[highest]:
            highest = risk
    return highest


def _review_action(package: dict[str, object]) -> str:
    review = package.get("review")
    if isinstance(review, dict) and isinstance(review.get("overallAction"), str):
        return str(review["overallAction"])
    return "human-review"


def _accepted_item_from_change(change: dict[str, object]) -> dict[str, object] | None:
    bundle = change.get("acceptedItem")
    if bundle is None:
        return None
    if not isinstance(bundle, dict):
        raise ValueError("acceptedItem must be an object")
    return _normalize_accepted_item_bundle(bundle)


def _accepted_workflow_from_change(change: dict[str, object]) -> dict[str, object] | None:
    bundle = change.get("acceptedWorkflow")
    if bundle is None:
        return None
    if not isinstance(bundle, dict):
        raise ValueError("acceptedWorkflow must be an object")
    return _normalize_accepted_workflow_bundle(bundle)


def _normalize_accepted_item_bundle(bundle: dict[str, object]) -> dict[str, object]:
    raw_item = bundle.get("item")
    if isinstance(raw_item, dict):
        item = dict(raw_item)
        for key in ["definitions", "attributes", "criteria", "examples"]:
            if key in bundle:
                item[key] = bundle[key]
        return item
    return dict(bundle)


def _normalize_accepted_workflow_bundle(bundle: dict[str, object]) -> dict[str, object]:
    raw_workflow = bundle.get("workflow")
    if isinstance(raw_workflow, dict):
        workflow = dict(raw_workflow)
    else:
        workflow = dict(bundle)

    workflow_id = _required_str(workflow, "workflow_id")
    for key in ["participants", "steps", "transitions", "exceptions", "metrics"]:
        records: list[dict[str, object]] = []
        for record in _mapping_list(bundle.get(key, workflow.get(key))):
            normalized = dict(record)
            normalized.setdefault("workflow_id", workflow_id)
            records.append(normalized)
        workflow[key] = records
    return workflow


def _workflow_ref_pairs(workflow: dict[str, object]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for label, key in [
        ("workflow.start_state_id", "start_state_id"),
        ("workflow.end_state_id", "end_state_id"),
        ("workflow.value_stage_id", "value_stage_id"),
    ]:
        value = _optional_any_str(workflow, key)
        if value is not None:
            refs.append((label, value))
    for business_object_id in _string_list(workflow.get("business_object_ids")):
        refs.append(("workflow.business_object_ids", business_object_id))

    for participant in _mapping_list(workflow.get("participants")):
        value = _optional_any_str(participant, "role_id")
        if value is not None:
            refs.append(("participant.role_id", value))

    for step in _mapping_list(workflow.get("steps")):
        value = _optional_any_str(step, "actor_id")
        if value is not None:
            refs.append(("step.actor_id", value))
        for input_id in _string_list(step.get("input_ids")):
            refs.append(("step.input_ids", input_id))
        for output_id in _string_list(step.get("output_ids")):
            refs.append(("step.output_ids", output_id))

    for transition in _mapping_list(workflow.get("transitions")):
        for label, key in [
            ("transition.from_state_id", "from_state_id"),
            ("transition.to_state_id", "to_state_id"),
            ("transition.authority_id", "authority_id"),
        ]:
            value = _optional_any_str(transition, key)
            if value is not None:
                refs.append((label, value))

    for metric in _mapping_list(workflow.get("metrics")):
        value = _optional_any_str(metric, "metric_id")
        if value is not None:
            refs.append(("metric.metric_id", value))
    return refs


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string field {key!r}")
    return value


def _required_any_str(mapping: dict[str, object], *keys: str) -> str:
    value = _optional_any_str(mapping, *keys)
    if value is None:
        raise ValueError(f"missing required string field from {keys!r}")
    return value


def _optional_any_str(mapping: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool):
        raise ValueError(f"missing required integer field {key!r}")
    if isinstance(value, int):
        return value
    raise ValueError(f"missing required integer field {key!r}")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _reject_raw_fields(mapping: dict[str, object]) -> None:
    forbidden = {
        "raw_payload",
        "rawPayload",
        "raw_value",
        "rawValue",
        "hidden_reasoning",
        "credential_value",
        "secret_value",
    }
    present = sorted(key for key in mapping if key in forbidden)
    if present:
        raise ValueError("raw or sensitive fields are not allowed: " + ", ".join(present))


def _safe_attribute_map(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        if key in {
            "raw_payload",
            "rawPayload",
            "raw_value",
            "rawValue",
            "hidden_reasoning",
            "credential_value",
            "secret_value",
        }:
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[key] = item
    return safe


def _json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str) -> dict[str, object]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("operational store expected a JSON object")
    return payload


def _row_dict(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def _version_entry(row: sqlite3.Row) -> dict[str, object]:
    """Overlay version columns on a stored payload for history queries."""

    entry = _json_loads(str(row["payload_json"]))
    entry["version_id"] = str(row["version_id"])
    entry["valid_to"] = row["valid_to"]
    entry["supersedes"] = row["supersedes"]
    entry["superseded_by"] = row["superseded_by"]
    return entry


def _package_summary(
    row: sqlite3.Row,
    *,
    current_revision: str | None = None,
) -> dict[str, object]:
    package = _json_loads(str(row["payload_json"]))
    review = package.get("review") if isinstance(package.get("review"), dict) else {}
    affected_ids: list[str] = []
    for change in _mapping_list(package.get("changes")):
        for affected_id in _string_list(change.get("affectedIds")):
            if affected_id not in affected_ids:
                affected_ids.append(affected_id)
    required_actions: list[dict[str, str]] = []
    if str(row["review_action"]) == "needs-owner":
        required_actions.append({"action": "needs-owner"})
    package_revision = str(package.get("ontologyRevision", ""))
    return {
        "packageId": str(row["package_id"]),
        "moduleId": str(row["module_id"]),
        "status": str(row["status"]),
        "summary": str(package.get("summary", "")),
        "risk": str(row["risk"]),
        "reviewAction": str(row["review_action"]),
        "owner": str(review.get("owner", "")),
        "createdAt": str(row["created_at"]),
        "requiredActions": required_actions,
        "sourceEventIds": _string_list(package.get("sourceEventIds")),
        "affectedIds": affected_ids,
        "ontologyRevision": package_revision,
        # Stale is only computable against a caller-provided current model
        # revision. Without one (or when the package carries no revision)
        # it stays False, matching the pre-detection behavior.
        "stale": _package_is_stale(package_revision, current_revision),
    }


def _package_is_stale(package_revision: str, current_revision: str | None) -> bool:
    return bool(
        current_revision
        and package_revision
        and package_revision != current_revision
    )


def _human_request_status(status: str) -> str:
    normalized = status.strip().lower().replace("_", "-")
    if normalized == "in-review":
        normalized = "open"
    if normalized == "resolved":
        normalized = "answered"
    if normalized not in HUMAN_REQUEST_STATUSES:
        raise ValueError(f"unsupported human request status {status!r}")
    return normalized


def _human_request_payload(request: dict[str, object]) -> dict[str, object]:
    return {
        "requestId": _required_any_str(request, "requestId", "request_id"),
        "kind": _required_str(request, "kind"),
        "status": _human_request_status(_optional_any_str(request, "status") or "open"),
        "owner": _optional_any_str(request, "owner") or "unknown",
        "channel": _optional_any_str(request, "channel") or "unknown",
        "messageRef": _optional_any_str(request, "messageRef", "message_ref") or "",
        "prompt": _required_str(request, "prompt"),
        "recommendedAnswer": _required_any_str(
            request,
            "recommendedAnswer",
            "recommended_answer",
            "recommendation",
        ),
        "blocks": _string_list(request.get("blocks")),
        "sourceRef": _optional_any_str(request, "sourceRef", "source_ref") or "",
        "packageId": _optional_any_str(request, "packageId", "package_id") or "",
        "askedAt": _optional_any_str(request, "askedAt", "asked_at") or "",
        "dueAt": _optional_any_str(request, "dueAt", "due_at") or "",
        "answeredAt": _optional_any_str(request, "answeredAt", "answered_at") or "",
        "answerSummary": _optional_any_str(request, "answerSummary", "answer_summary") or "",
        "decisionId": _optional_any_str(request, "decisionId", "decision_id") or "",
    }


def _human_request_row(row: sqlite3.Row) -> dict[str, object]:
    blocks_payload = _json_loads(str(row["blocks_json"]))
    return {
        "requestId": str(row["request_id"]),
        "kind": str(row["kind"]),
        "status": str(row["status"]),
        "owner": str(row["owner"]),
        "channel": str(row["channel"]),
        "messageRef": str(row["message_ref"]),
        "prompt": str(row["prompt"]),
        "recommendedAnswer": str(row["recommended_answer"]),
        "blocks": _string_list(blocks_payload.get("blocks")),
        "sourceRef": str(row["source_ref"]),
        "packageId": "" if row["package_id"] is None else str(row["package_id"]),
        "askedAt": str(row["asked_at"]),
        "dueAt": "" if row["due_at"] is None else str(row["due_at"]),
        "answeredAt": "" if row["answered_at"] is None else str(row["answered_at"]),
        "answerSummary": str(row["answer_summary"]),
        "decisionId": "" if row["decision_id"] is None else str(row["decision_id"]),
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"]),
    }


def _definition_row(row: sqlite3.Row) -> dict[str, object]:
    return _json_loads(str(row["payload_json"]))


def _attribute_row(row: sqlite3.Row) -> dict[str, object]:
    attribute = _json_loads(str(row["payload_json"]))
    allowed_values = _json_loads(str(row["allowed_values_json"]))
    attribute["allowed_values"] = _string_list(allowed_values.get("allowed_values"))
    return attribute


def _workflow_step_row(row: sqlite3.Row) -> dict[str, object]:
    step = _json_loads(str(row["payload_json"]))
    input_ids = _json_loads(str(row["input_ids_json"]))
    output_ids = _json_loads(str(row["output_ids_json"]))
    step["input_ids"] = _string_list(input_ids.get("input_ids"))
    step["output_ids"] = _string_list(output_ids.get("output_ids"))
    return step


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
