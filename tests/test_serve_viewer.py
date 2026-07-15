import hashlib
from http import HTTPStatus
from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import serve_viewer  # noqa: E402


class ServeViewerTests(unittest.TestCase):
    def make_viewer(self, root: Path, *, privacy_status: str = "passed") -> tuple[Path, str]:
        viewer = root / "viewer"
        viewer.mkdir()
        bundle_text = '{"module":"test"}\n'
        bundle_hash = hashlib.sha256(bundle_text.encode("utf-8")).hexdigest()[:16]
        bundle_name = f"ontology.{bundle_hash}.json"
        (viewer / "index.html").write_text("<html>official</html>", encoding="utf-8")
        (viewer / bundle_name).write_text(bundle_text, encoding="utf-8")
        (viewer / "ontology.json").write_text(bundle_text, encoding="utf-8")
        (viewer / "ontology.0000000000000000.json").write_text(
            '{"stale":"private"}\n', encoding="utf-8"
        )
        (viewer / "VIEWER_PUBLISH_REPORT.json").write_text(
            json.dumps(
                {
                    "status": "published",
                    "bundle": bundle_name,
                    "bundle_hash": "sha256:"
                    + hashlib.sha256(bundle_text.encode("utf-8")).hexdigest(),
                    "viewer_asset_hash": "sha256:"
                    + hashlib.sha256(b"<html>official</html>").hexdigest(),
                    "privacy": {
                        "status": privacy_status,
                        "policy": "public-viewer-v1",
                    },
                }
            ),
            encoding="utf-8",
        )
        return viewer, bundle_name

    def with_server(self, viewer: Path):
        server = serve_viewer.create_server(viewer, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, f"http://127.0.0.1:{server.server_address[1]}"

    def test_serves_only_current_allowlisted_files_without_directory_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            viewer, bundle_name = self.make_viewer(Path(tmp))
            server, thread, base = self.with_server(viewer)
            try:
                with urlopen(base + "/", timeout=3) as response:
                    self.assertEqual(response.status, HTTPStatus.OK)
                    self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
                with urlopen(base + "/" + bundle_name, timeout=3) as response:
                    self.assertEqual(response.status, HTTPStatus.OK)
                with self.assertRaises(HTTPError) as stale:
                    urlopen(base + "/ontology.0000000000000000.json", timeout=3)
                self.assertEqual(stale.exception.code, HTTPStatus.NOT_FOUND)
                with self.assertRaises(HTTPError) as listing:
                    urlopen(base + "/subdirectory/", timeout=3)
                self.assertEqual(listing.exception.code, HTTPStatus.NOT_FOUND)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_refuses_all_viewer_files_without_passed_privacy_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            viewer, _bundle_name = self.make_viewer(Path(tmp), privacy_status="failed")
            server, thread, base = self.with_server(viewer)
            try:
                with self.assertRaises(HTTPError) as blocked:
                    urlopen(base + "/", timeout=3)
                self.assertEqual(blocked.exception.code, HTTPStatus.SERVICE_UNAVAILABLE)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
