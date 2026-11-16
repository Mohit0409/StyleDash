"""Vibe4You production Firebase cleanup helper contract, all-mocked tests."""
import hashlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import styledash_firebase as firebase

ROOT=Path(__file__).resolve().parents[2]
EXPECTED_SHA="5a18168d383099a744d20ed2d4937f7103d6590f110da0b63b9563a4b1d563ed"


class FirebaseCleanupContract(unittest.TestCase):
    def test_exact_production_module_hash(self):
        data=(ROOT/"scripts/styledash_firebase.py").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),EXPECTED_SHA)

    def test_invalid_user_ids_do_not_initialize_firebase(self):
        with patch.object(firebase,"_initialize_app") as init:
            for uid in ("", "u" * 129, None, 123, []):
                with self.subTest(uid_type=type(uid).__name__):
                    firebase.delete_firebase_user(uid)
            init.assert_not_called()

    def test_valid_user_is_deleted_only_through_mocked_sdk(self):
        app=object()
        delete=Mock()
        class NotFound(Exception):
            pass
        fake_auth=types.SimpleNamespace(
            delete_user=delete,UserNotFoundError=NotFound)
        fake_sdk=types.ModuleType("firebase_admin")
        fake_sdk.auth=fake_auth
        with patch.object(firebase,"_initialize_app",return_value=app),\
             patch.dict(sys.modules,{"firebase_admin":fake_sdk}):
            firebase.delete_firebase_user("synthetic-uid-123")
        delete.assert_called_once_with("synthetic-uid-123",app=app)

    def test_already_deleted_user_is_idempotent(self):
        class NotFound(Exception):
            pass
        fake_auth=types.SimpleNamespace(
            delete_user=Mock(side_effect=NotFound()),
            UserNotFoundError=NotFound)
        fake_sdk=types.ModuleType("firebase_admin")
        fake_sdk.auth=fake_auth
        with patch.object(firebase,"_initialize_app",return_value=object()),\
             patch.dict(sys.modules,{"firebase_admin":fake_sdk}):
            self.assertIsNone(firebase.delete_firebase_user("synthetic-uid-123"))

    def test_other_errors_are_not_hidden(self):
        class NotFound(Exception):
            pass
        fake_auth=types.SimpleNamespace(
            delete_user=Mock(side_effect=RuntimeError("synthetic backend outage")),
            UserNotFoundError=NotFound)
        fake_sdk=types.ModuleType("firebase_admin")
        fake_sdk.auth=fake_auth
        with patch.object(firebase,"_initialize_app",return_value=object()),\
             patch.dict(sys.modules,{"firebase_admin":fake_sdk}):
            with self.assertRaisesRegex(RuntimeError,"synthetic backend outage"):
                firebase.delete_firebase_user("synthetic-uid-123")


if __name__=="__main__":
    unittest.main()
