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

    def close(self) -> None:
        self._connection.close()

    def initialize(self) -> None:
        self._connection.executescript(
            """
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
                item_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                name TEXT NOT NULL,
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

            CREATE TABLE IF NOT EXISTS accepted_definitions (
                definition_id TEXT PRIMARY KEY,
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
                updated_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES accepted_items(item_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_attributes (
                attribute_id TEXT PRIMARY KEY,
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
                updated_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES accepted_items(item_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_criteria (
                criterion_id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                criterion_type TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                text TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES accepted_items(item_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_examples (
                example_id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                example_type TEXT NOT NULL,
                text TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES accepted_items(item_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_workflows (
                workflow_id TEXT PRIMARY KEY,
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
                last_verified_at TEXT NOT NULL,
                confidence TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_participants (
                participant_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                role_id TEXT NOT NULL,
                participant_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES accepted_workflows(workflow_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_steps (
                step_id TEXT PRIMARY KEY,
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
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES accepted_workflows(workflow_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_transitions (
                transition_id TEXT PRIMARY KEY,
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
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES accepted_workflows(workflow_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_exceptions (
                exception_id TEXT PRIMARY KEY,
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
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES accepted_workflows(workflow_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accepted_workflow_metrics (
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
                PRIMARY KEY (workflow_id, metric_id),
                FOREIGN KEY (workflow_id) REFERENCES accepted_workflows(workflow_id)
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

            CREATE TABLE IF NOT EXISTS review_questions (
                question_id TEXT PRIMARY KEY,
                package_id TEXT NOT NULL,
                status TEXT NOT NULL,
                prompt TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (package_id) REFERENCES model_change_packages(package_id)
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
            CREATE INDEX IF NOT EXISTS idx_review_questions_status
                ON review_questions(status, updated_at, question_id);
            CREATE INDEX IF NOT EXISTS idx_source_cursors_source
                ON source_cursors(source_id, cursor_key);
            """
        )
        self._connection.commit()

    def record_accepted_item(self, item: dict[str, object]) -> str:
        """Persist one accepted model item and its semantic detail records."""

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
        now = _now()

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO accepted_items (
                    item_id, kind, status, name, source_id, evidence_id,
                    decision_id, valid_from, valid_to, last_verified_at,
                    confidence, payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id)
                DO UPDATE SET kind = excluded.kind,
                              status = excluded.status,
                              name = excluded.name,
                              source_id = excluded.source_id,
                              evidence_id = excluded.evidence_id,
                              decision_id = excluded.decision_id,
                              valid_from = excluded.valid_from,
                              valid_to = excluded.valid_to,
                              last_verified_at = excluded.last_verified_at,
                              confidence = excluded.confidence,
                              payload_json = excluded.payload_json,
                              updated_at = excluded.updated_at
                """,
                (
                    item_id,
                    kind,
                    status,
                    name,
                    source_id,
                    evidence_id,
                    decision_id,
                    valid_from,
                    valid_to,
                    last_verified_at,
                    confidence,
                    _json_dumps(item),
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

    def get_accepted_item(self, item_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """
            SELECT payload_json
              FROM accepted_items
             WHERE item_id = ?
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
        """Persist one accepted process workflow and its structured children."""

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
        now = _now()

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO accepted_workflows (
                    workflow_id, name, status, owner, source_id, evidence_id,
                    decision_id, start_state_id, end_state_id, valid_from,
                    valid_to, last_verified_at, confidence, payload_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id)
                DO UPDATE SET name = excluded.name,
                              status = excluded.status,
                              owner = excluded.owner,
                              source_id = excluded.source_id,
                              evidence_id = excluded.evidence_id,
                              decision_id = excluded.decision_id,
                              start_state_id = excluded.start_state_id,
                              end_state_id = excluded.end_state_id,
                              valid_from = excluded.valid_from,
                              valid_to = excluded.valid_to,
                              last_verified_at = excluded.last_verified_at,
                              confidence = excluded.confidence,
                              payload_json = excluded.payload_json,
                              updated_at = excluded.updated_at
                """,
                (
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
                    last_verified_at,
                    confidence,
                    _json_dumps(workflow),
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
        row = self._connection.execute(
            """
            SELECT payload_json
              FROM accepted_workflows
             WHERE workflow_id = ?
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

    def apply_approved_model_change(self, package: dict[str, object]) -> dict[str, list[str]]:
        """Apply approved accepted-state payloads from a model-change package."""

        package_id = _required_str(package, "packageId")
        package_status = self._package_status(package_id)
        if package_status != "approved":
            raise ValueError(f"model change package {package_id} is not approved")

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

    def list_pending_packages(self, *, limit: int = 50) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """
            SELECT package_id, module_id, risk, review_action, payload_json
              FROM model_change_packages
             WHERE status = 'pending'
             ORDER BY created_at ASC, package_id ASC
             LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [_package_summary(row) for row in rows]

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

    def list_open_questions(self, *, limit: int = 50) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """
            SELECT question_id, package_id, status, prompt, recommendation,
                   created_at, updated_at
              FROM review_questions
             WHERE status IN ('open', 'in-review')
             ORDER BY updated_at ASC, question_id ASC
             LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [_row_dict(row) for row in rows]

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
            "source_events",
            "model_change_packages",
            "package_source_events",
            "package_evidence",
            "package_affected_ids",
            "review_questions",
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
    ]:
        value = _optional_any_str(workflow, key)
        if value is not None:
            refs.append((label, value))

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


def _json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str) -> dict[str, object]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("operational store expected a JSON object")
    return payload


def _row_dict(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def _package_summary(row: sqlite3.Row) -> dict[str, object]:
    package = _json_loads(str(row["payload_json"]))
    affected_ids: list[str] = []
    for change in _mapping_list(package.get("changes")):
        for affected_id in _string_list(change.get("affectedIds")):
            if affected_id not in affected_ids:
                affected_ids.append(affected_id)
    return {
        "packageId": str(row["package_id"]),
        "moduleId": str(row["module_id"]),
        "summary": str(package.get("summary", "")),
        "risk": str(row["risk"]),
        "reviewAction": str(row["review_action"]),
        "sourceEventIds": _string_list(package.get("sourceEventIds")),
        "affectedIds": affected_ids,
        "ontologyRevision": str(package.get("ontologyRevision", "")),
        "stale": False,
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
