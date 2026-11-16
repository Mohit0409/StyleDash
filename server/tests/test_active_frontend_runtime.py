"""Offline public runtime integrity and provenance regression tests."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify_pinned_frontend_runtime as frontend


class ActiveFrontendRuntimeTests(unittest.TestCase):
    def test_all_133_public_files_match_pinned_runtime_snapshot(self):
        result=frontend.verify()
        self.assertEqual(result,{
            "files":133,
            "pinned":123,
            "unmanifested":10,
            "index_direct_refs":21,
            "potential_vite_assets":123,
        })

    def test_search_v2_main_bundle_is_sha_pinned(self):
        bundle=frontend.SITE/"assets/index-MMTPd8z_-v4y-search-v2-r2.js"
        self.assertEqual(len(bundle.read_bytes()),269668)
        self.assertEqual(
            hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "2d61891edd2ed343de5f75d92955e65c1bab913e5885547ec977e24430150a4e",
        )

    def test_unmanifested_live_assets_are_not_misrepresented_as_tracked(self):
        meta=json.loads(frontend.MANIFEST.read_text("utf-8"))
        missing={x["target"] for x in meta["files"]
                 if not x["production_integrity_manifest"]}
        expected={
            "server/assets/Home-bVIr0YEJ.css",
            "server/assets/index-BITtbtpM.css",
            "server/sw.js",
            "server/vibe4you-app/icons/apple-touch-icon.png",
            "server/vibe4you-app/icons/icon-192.png",
            "server/vibe4you-app/icons/icon-512.png",
            "server/vibe4you-app/icons/icon-maskable-512.png",
            "server/vibe4you-app/manifest.json",
            "server/vibe4you-app/pwa-install.css",
            "server/vibe4you-app/pwa-install.js",
        }
        self.assertEqual(missing,expected)

    def test_path_traversal_private_files_and_extensions_are_denied(self):
        for path in (
            "../private.py","server/../../data/orders.json",
            "server/.env","server/admin/payments.sqlite",
            "server/assets/private.key","server/customer-data/orders.json",
            "C:/windows/system32.dll","/etc/passwd",
        ):
            with self.subTest(path=path):
                with self.assertRaises(frontend.FrontendCapsuleError):
                    frontend.clean_target_path(path)

    def test_mutated_asset_bytes_fail_closed(self):
        meta=json.loads(frontend.MANIFEST.read_text("utf-8"))
        target=next(x for x in meta["files"] if
                    x["target"]=="server/assets/seller-price-labels-20261018.js")
        with tempfile.TemporaryDirectory(prefix="v4y-public-tamper-") as temp:
            base=Path(temp)
            file=base/"assets/seller-price-labels-20261018.js"
            file.parent.mkdir(parents=True)
            file.write_bytes(
                (frontend.SITE/"assets/seller-price-labels-20261018.js").read_bytes()+b"\n"
            )
            with self.assertRaisesRegex(frontend.FrontendCapsuleError,"byte/hash mismatch"):
                frontend.check_file(target,base)

    def test_manifest_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="v4y-asset-map-tamper-") as temp:
            altered=Path(temp)/"asset-manifest.json"
            altered.write_bytes(frontend.MANIFEST.read_bytes()+b" ")
            with patch.object(frontend,"MANIFEST",altered):
                with self.assertRaisesRegex(frontend.FrontendCapsuleError,"manifest has changed"):
                    frontend.verify()

    def test_pwa_icon_files_have_png_signatures_and_service_worker_exists(self):
        pwa=json.loads((frontend.SITE/"vibe4you-app/manifest.json").read_text("utf-8"))
        self.assertEqual(len(pwa.get("icons",[])),3)
        for image in pwa["icons"]:
            with self.subTest(name=image["src"]):
                file=frontend.SITE/image["src"].lstrip("/")
                self.assertEqual(file.read_bytes()[:8],b"\x89PNG\r\n\x1a\n")
        self.assertIn("self", (frontend.SITE/"sw.js").read_text("utf-8"))

    def test_index_links_resolve_to_local_public_capsule(self):
        p=frontend.HomeReferences()
        p.feed((frontend.SITE/"index.html").read_text("utf-8"))
        self.assertEqual(len(p.refs),21)
        for ref in p.refs:
            self.assertTrue((frontend.SITE/ref.removeprefix("server/")).is_file(),ref)


if __name__=="__main__":
    unittest.main()
