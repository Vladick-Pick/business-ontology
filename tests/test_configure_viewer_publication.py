import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import configure_viewer_publication as configure


class ConfigureViewerPublicationTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        viewer = workspace / "viewer"
        viewer.mkdir(parents=True)
        (workspace / "runtime-config.json").write_text(
            json.dumps({"viewer_output_path": "viewer"}) + "\n",
            encoding="utf-8",
        )
        (viewer / "VIEWER_PUBLISH_REPORT.json").write_text(
            json.dumps(
                {
                    "status": "published",
                    "bundle": "ontology.0123456789abcdef.json",
                    "privacy": {"status": "passed", "policy": "public-viewer-v1"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return workspace

    def test_workspace_only_updates_runtime_config_without_host_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))

            result = configure.configure(
                workspace,
                mode="workspace-only",
                public_url=None,
                route_path=None,
                tailscale_bin="tailscale",
                apply=True,
            )
            first_bytes = (workspace / "runtime-config.json").read_bytes()
            replay = configure.configure(
                workspace,
                mode="workspace-only",
                public_url=None,
                route_path=None,
                tailscale_bin="tailscale",
                apply=True,
            )

            config = json.loads((workspace / "runtime-config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["viewer_publication"]["mode"], "workspace-only")
            self.assertEqual(config["viewer_publication"]["public_url"], "")
            self.assertEqual(result["verification"]["status"], "workspace-only")
            self.assertFalse(replay["changed"])
            self.assertEqual((workspace / "runtime-config.json").read_bytes(), first_bytes)

    def test_static_url_requires_credential_free_https(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))

            with self.assertRaises(configure.PublicationConfigurationError):
                configure.configure(
                    workspace,
                    mode="static-url",
                    public_url="http://example.test/model",
                    route_path=None,
                    tailscale_bin="tailscale",
                    apply=False,
                )

    def test_tailscale_funnel_preserves_other_routes_and_verifies_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            status = {
                "Web": {
                    "agent.tailnet.test:443": {
                        "Handlers": {"/": {"Proxy": "http://127.0.0.1:8766"}}
                    }
                }
            }
            with (
                mock.patch.object(
                    configure,
                    "_run_json",
                    side_effect=[
                        {"Self": {"DNSName": "agent.tailnet.test."}},
                        status,
                    ],
                ),
                mock.patch.object(configure, "_run_mutation") as mutation,
                mock.patch.object(
                    configure,
                    "_install_service",
                    return_value={
                        "name": "business-ontology-viewer-business-analyst-interlab.service",
                        "unit_path": Path(tmp) / "viewer.service",
                        "previous": None,
                        "was_enabled": False,
                        "was_active": False,
                    },
                ),
                mock.patch.object(
                    configure,
                    "_verified_existing_report",
                    return_value={
                        "status": "verified",
                        "public_url": "https://agent.tailnet.test/models/interlab/",
                        "verified_at": "2026-07-15T08:00:00Z",
                    },
                ) as verified,
            ):
                result = configure.configure(
                    workspace,
                    mode="tailscale-funnel",
                    public_url=None,
                    route_path="/models/interlab/",
                    tailscale_bin="/usr/bin/tailscale",
                    apply=True,
                    agent_id="business-analyst-interlab",
                    user_unit_dir=Path(tmp) / "systemd",
                )

            port = configure.default_local_port("business-analyst-interlab")
            mutation.assert_called_once_with(
                "/usr/bin/tailscale",
                [
                    "funnel",
                    "--bg",
                    "--yes",
                    "--set-path",
                    "/models/interlab",
                    f"http://127.0.0.1:{port}",
                ],
            )
            self.assertEqual(verified.call_count, 2)
            self.assertEqual(
                verified.call_args_list[0].args[1],
                f"http://127.0.0.1:{port}/",
            )
            self.assertEqual(
                result["target"]["public_url"],
                "https://agent.tailnet.test/models/interlab/",
            )
            self.assertEqual(result["target"]["local_port"], port)
            report = json.loads(
                (workspace / "viewer" / "VIEWER_PUBLISH_REPORT.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(report["publication"]["status"], "verified")

    def test_tailscale_refuses_a_path_owned_by_another_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            status = {
                "Handlers": {
                    "/models/interlab": {"Path": "/srv/someone-else"},
                }
            }
            with mock.patch.object(
                configure,
                "_run_json",
                side_effect=[
                    {"Self": {"DNSName": "agent.tailnet.test."}},
                    status,
                ],
            ):
                with self.assertRaises(configure.PublicationConfigurationError):
                    configure.configure(
                        workspace,
                        mode="tailscale-funnel",
                        public_url=None,
                        route_path="/models/interlab",
                        tailscale_bin="tailscale",
                        apply=False,
                        agent_id="business-analyst-interlab",
                    )


if __name__ == "__main__":
    unittest.main()
