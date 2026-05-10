import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inc.db import PhosphorDB


class TestPhosphorDB(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = PhosphorDB(self._tmp.name)

    def tearDown(self):
        self.db.close()
        os.unlink(self._tmp.name)

    def test_table_created(self):
        cur = self.db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        self.assertIn("results", tables)

    def test_record_inserts_row(self):
        self.db.record("host:3270", "app", "abc", "app_auth")
        cur = self.db._conn.execute("SELECT * FROM results")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 1)

    def test_record_fields(self):
        self.db.record(
            "host:3270", "app", "abc", "app_auth", username="uid1", environment="env1"
        )
        cur = self.db._conn.execute(
            "SELECT run_id, mode, code, response, username, environment FROM results"
        )
        row = cur.fetchone()
        self.assertEqual(row[0], "host:3270")
        self.assertEqual(row[1], "app")
        self.assertEqual(row[2], "abc")
        self.assertEqual(row[3], "app_auth")
        self.assertEqual(row[4], "uid1")
        self.assertEqual(row[5], "env1")

    def test_multiple_records(self):
        self.db.record("h:1", "user", "usr1", "user_valid")
        self.db.record("h:1", "user", "usr2", "user_invalid")
        cur = self.db._conn.execute("SELECT COUNT(*) FROM results")
        self.assertEqual(cur.fetchone()[0], 2)

    def test_close_is_idempotent(self):
        self.db.close()
        self.db.close()

    def test_optional_fields_default_none(self):
        self.db.record("h:1", "cics", "CESN", "cics_auth")
        cur = self.db._conn.execute("SELECT username, environment FROM results")
        row = cur.fetchone()
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])


if __name__ == "__main__":
    unittest.main()
