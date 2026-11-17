import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import db_connect_args


class DbConnectTests(unittest.TestCase):
    def test_postgres_connect_times_out(self):
        args = db_connect_args("postgresql+psycopg://scanner:scanner@localhost:5432/scanner")
        self.assertEqual(args["connect_timeout"], 10)

    def test_sqlite_keeps_thread_check_only(self):
        args = db_connect_args("sqlite:///./scanner.local.db")
        self.assertEqual(args, {"check_same_thread": False})


if __name__ == "__main__":
    unittest.main()
