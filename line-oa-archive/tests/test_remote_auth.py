import http.client
import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from admin_server import AdminServer
from remote_auth import RemoteAccess


class RemoteAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.settings = {"ADMIN_PUBLIC_HOST": "admin.example.com", "CF_ACCESS_TEAM_DOMAIN": "test.cloudflareaccess.com",
                         "CF_ACCESS_AUD": "test-audience", "ADMIN_ALLOWED_EMAILS": "admin@example.com"}
        env = patch.dict(os.environ, self.settings, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.access = RemoteAccess()
        keys = patch.object(self.access.keys, "get_signing_key_from_jwt", return_value=SimpleNamespace(key=self.key.public_key()))
        self.keys = keys.start()
        self.addCleanup(keys.stop)

    def token(self, **overrides):
        claims = {"exp": int(time.time()) + 300, "iat": int(time.time()) - 1, "iss": self.access.issuer,
                  "aud": self.access.audience, "sub": "test-user", "email": "admin@example.com"}
        claims.update(overrides)
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "test-key"})

    def test_valid_signature_and_allowed_email(self):
        self.assertEqual(self.access.verify(self.token(email="ADMIN@example.com")), "admin@example.com")

    def test_reject_expiry_audience_issuer_email_missing_claim_and_future_token(self):
        for change in ({"exp": 1}, {"aud": "another-app"}, {"iss": "https://evil.example"},
                       {"email": "other@example.com"}, {"email": None}, {"sub": None},
                       {"iat": int(time.time()) + 600}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.access.verify(self.token(**change))
        claims = jwt.decode(self.token(), options={"verify_signature": False})
        del claims["exp"]
        with self.assertRaises(ValueError):
            self.access.verify(jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "test-key"}))

    def test_reject_wrong_signature_algorithm_and_unavailable_keys(self):
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = jwt.decode(self.token(), options={"verify_signature": False})
        for token in ("", "malformed", jwt.encode(claims, wrong_key, algorithm="RS256", headers={"kid": "test-key"}),
                      jwt.encode(claims, "x" * 32, algorithm="HS256", headers={"kid": "test-key"})):
            with self.subTest(token_length=len(token)), self.assertRaises(ValueError):
                self.access.verify(token)
        self.keys.side_effect = jwt.PyJWKClientError("offline")
        with self.assertRaises(ValueError):
            self.access.verify(self.token())

    def test_incomplete_or_untrusted_configuration_is_disabled(self):
        for key in self.settings:
            with self.subTest(key=key), patch.dict(os.environ, {key: ""}):
                self.assertFalse(RemoteAccess().enabled)
        with patch.dict(os.environ, {"CF_ACCESS_TEAM_DOMAIN": "evil.example"}):
            self.assertFalse(RemoteAccess().enabled)

    def test_http_auth_and_csrf_boundaries(self):
        server = AdminServer(0)
        server.remote_access = self.access
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(headers, method="GET", path="/api/session"):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                conn.request(method, path, body="{}" if method == "POST" else None, headers=headers)
                response = conn.getresponse()
                response.read()
                return response.status
            finally:
                conn.close()
        try:
            valid = {"Host": self.access.host, "X-Forwarded-Proto": "https", "Cf-Access-Jwt-Assertion": self.token()}
            self.assertEqual(request(valid), 200)
            self.assertEqual(request({"Authorization": "Bearer " + server.token}), 200)
            self.assertEqual(request({}), 401)
            self.assertEqual(request({**valid, "Cf-Access-Jwt-Assertion": ""}), 403)
            self.assertEqual(request({**valid, "Host": "evil.example"}), 403)
            self.assertEqual(request({**valid, "X-Forwarded-Proto": "http"}), 403)
            self.assertEqual(request({**valid, "Origin": "https://evil.example"}), 403)
            self.assertEqual(request({"Authorization": "Bearer " + server.token, "X-Forwarded-For": "1.2.3.4"}), 403)
            # Static pages also require a valid remote identity.
            self.assertEqual(request({**valid, "Cf-Access-Jwt-Assertion": ""}, path="/"), 403)
            self.assertEqual(request(valid, "POST", "/api/not-found"), 403)
            self.assertEqual(request({**valid, "Origin": "https://" + self.access.host, "Content-Type": "application/json"}, "POST", "/api/not-found"), 404)
            server.remote_access.enabled = False
            self.assertEqual(request(valid), 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
