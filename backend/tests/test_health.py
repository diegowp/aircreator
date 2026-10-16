"""Test basic application startup and health endpoint."""

import unittest
from app.core.config import settings


class TestHealth(unittest.TestCase):
    def test_settings_loaded(self):
        self.assertEqual(settings.app_name, "AirCreator API")
        self.assertEqual(settings.app_version, "0.1.0")
        self.assertEqual(settings.api_prefix, "/api/v1")


if __name__ == "__main__":
    unittest.main()
