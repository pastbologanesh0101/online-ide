"""Unit tests for db.py -- snippet save/load round trip."""

from __future__ import annotations

import os
import tempfile
import unittest

import db


class TestSnippetStorage(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_save_then_load_round_trips_exact_source_code(self):
        source = "def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n"
        db.save_snippet("adder", source, self.db_path)
        loaded = db.load_snippet("adder", self.db_path)
        self.assertEqual(loaded, source)

    def test_load_missing_snippet_returns_none(self):
        self.assertIsNone(db.load_snippet("does-not-exist", self.db_path))

    def test_save_overwrites_existing_snippet_with_same_name(self):
        db.save_snippet("s1", "print(1)", self.db_path)
        db.save_snippet("s1", "print(2)", self.db_path)
        self.assertEqual(db.load_snippet("s1", self.db_path), "print(2)")

    def test_list_snippets_returns_saved_names(self):
        db.save_snippet("alpha", "print('a')", self.db_path)
        db.save_snippet("beta", "print('b')", self.db_path)
        names = {s["name"] for s in db.list_snippets(self.db_path)}
        self.assertEqual(names, {"alpha", "beta"})

    def test_delete_snippet_removes_it(self):
        db.save_snippet("temp", "print('gone soon')", self.db_path)
        self.assertTrue(db.delete_snippet("temp", self.db_path))
        self.assertIsNone(db.load_snippet("temp", self.db_path))


if __name__ == "__main__":
    unittest.main()
