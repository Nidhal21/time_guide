import os
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.auth_service import ensure_auth_tables, login_user, signup_user


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        os.environ["ADMIN_EMAIL"] = "admin@example.com"
        os.environ["ADMIN_PASSWORD"] = "admin-secret"
        os.environ["ADMIN_FULL_NAME"] = "Admin ENETCOM"

        self.engine = create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.Session = sessionmaker(bind=self.connection)
        self.db = self.Session()
        ensure_auth_tables(self.db)

    def tearDown(self):
        self.db.close()
        self.connection.close()
        self.engine.dispose()

    def test_signup_creates_user_session(self):
        result = signup_user(self.db, email="student@example.com", password="secret123", full_name="Student Test")
        self.assertEqual(result["user"]["role"], "user")
        self.assertEqual(result["user"]["email"], "student@example.com")
        self.assertTrue(result["session"]["access_token"])

    def test_login_user_after_signup(self):
        signup_user(self.db, email="student2@example.com", password="secret123", full_name="Student Two")
        result = login_user(self.db, email="student2@example.com", password="secret123")
        self.assertEqual(result["user"]["role"], "user")
        self.assertEqual(result["user"]["email"], "student2@example.com")

    def test_login_admin_uses_configured_credentials(self):
        result = login_user(self.db, email="admin@example.com", password="admin-secret")
        self.assertEqual(result["user"]["role"], "admin")
        self.assertEqual(result["user"]["email"], "admin@example.com")


if __name__ == "__main__":
    unittest.main()
