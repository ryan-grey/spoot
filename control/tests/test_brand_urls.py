from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from greybot_control.web import create_app
from test_control import Base, FakeDiscord


class BrandURLTests(Base):
    def setUp(self):
        super().setUp()
        self.cfg = replace(self.cfg, origin="https://spoot.ryangrey.dev")
        self.client = TestClient(create_app(self.cfg, self.store, FakeDiscord()),
                                 base_url=self.cfg.origin, follow_redirects=False)
        self.addCleanup(self.client.close)

    def test_old_deep_links_preserve_path_and_query(self):
        for method in ("GET", "HEAD"):
            response = self.client.request(method, "https://greybot.ryangrey.dev/raids?event=42&tab=roster")
            self.assertEqual(response.status_code, 308)
            self.assertEqual(response.headers["location"], self.cfg.origin + "/raids?event=42&tab=roster")

    def test_old_callback_restarts_without_forwarding_oauth_credentials(self):
        response = self.client.get("https://greybot.ryangrey.dev/auth/callback?code=old-code&state=old-state")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], self.cfg.origin + "/auth/login")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")

    def test_new_login_uses_new_callback_and_keeps_state_cookie(self):
        response = self.client.get("/auth/login")
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["redirect_uri"], [self.cfg.origin + "/auth/callback"])
        self.assertIn("__Host-greybot-login", response.cookies)

    def test_legacy_posts_reach_validation_without_redirect_or_access_bypass(self):
        response = self.client.post("https://greybot.ryangrey.dev/discord/roles", json={})
        self.assertNotIn("location", response.headers)
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(self.client.get("/api/status").status_code, 401)
        self.assertEqual(self.client.get("https://untrusted.example/about").status_code, 400)

    def test_new_public_page_is_served_directly(self):
        self.assertEqual(self.client.get("/about").status_code, 200)
