from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_validator(path, *args):
    return subprocess.run(
        [sys.executable, "scripts/links_validate.py", str(path), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


class InvalidFixtureTests(unittest.TestCase):
    def assert_fixture_fails(self, fixture, expected, *args):
        result = run_validator(Path("fixtures/invalid") / fixture, *args)
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(expected, output)

    def test_dangling_link(self):
        self.assert_fixture_fails("dangling-link", "dangling link measured-by")

    def test_bad_relation(self):
        self.assert_fixture_fails("bad-relation", "relation 'depends-on'")

    def test_duplicate_id(self):
        self.assert_fixture_fails("duplicate-id", "duplicate id 'duplicated-card'")

    def test_missing_status(self):
        self.assert_fixture_fails("missing-status", "missing required field 'status'")

    def test_derived_id(self):
        self.assert_fixture_fails("derived-id", "contains '--'")

    def test_malformed_yaml_list(self):
        self.assert_fixture_fails("malformed-yaml-list", "malformed mapping line")

    def test_interface_missing_participant(self):
        self.assert_fixture_fails(
            "interface-missing-participant",
            "attrs.participants.subject must be a non-empty list",
        )

    def test_decision_missing_attrs(self):
        self.assert_fixture_fails("decision-missing-attrs", "missing required attrs.scope")

    def test_extra_frontmatter_key(self):
        self.assert_fixture_fails(
            "extra-frontmatter-key",
            "top-level key 'subtype' is outside the card contract",
        )

    def test_staged_pii(self):
        self.assert_fixture_fails("staged-pii", "possible email address", "--staged")

    def test_unregistered_source(self):
        self.assert_fixture_fails(
            "unregistered-source",
            "source 'missing-source' is not registered",
        )

    def test_trust_floor_laundering(self):
        self.assert_fixture_fails(
            "trust-floor-laundering",
            "status 'accepted' exceeds source trust floor 'hypothesis'",
        )

    def test_missing_source_map(self):
        self.assert_fixture_fails(
            "missing-source-map",
            "no 02-source-map.md applies",
        )

    def test_unsafe_source_policy(self):
        self.assert_fixture_fails(
            "unsafe-source-policy",
            "read policy piiExcluded must be true",
        )
        self.assert_fixture_fails(
            "unsafe-source-policy",
            "read policy rawPayloadAccess must be false",
        )

    def test_staged_trust_upgrade(self):
        self.assert_fixture_fails(
            "staged-trust-upgrade",
            "status 'accepted' exceeds source trust floor 'candidate'",
            "--staged",
        )

    def test_measured_by_requires_metric_target(self):
        self.assert_fixture_fails(
            "link-measured-by-non-metric",
            "semantic link measured-by -> 'not-a-metric' target must be a concept",
        )

    def test_source_of_truth_direction_is_checked(self):
        self.assert_fixture_fails(
            "link-source-of-truth-backwards",
            "semantic link source-of-truth from 'crm' must start",
        )

    def test_in_state_requires_state_target(self):
        self.assert_fixture_fails(
            "link-in-state-non-state",
            "semantic link in-state -> 'not-a-state' target must be type 'state'",
        )

    def test_part_of_requires_structural_endpoints(self):
        self.assert_fixture_fails(
            "link-part-of-invalid-type",
            "semantic link part-of from 'lead-quality' must start",
        )


if __name__ == "__main__":
    unittest.main()
