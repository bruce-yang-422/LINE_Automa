"""Verify Cloudflare Access application tokens before allowing remote administration."""

import os
import re
import ssl
import threading

import jwt
import truststore


class RemoteAccess:
    def __init__(self):
        self.host = os.environ.get("ADMIN_PUBLIC_HOST", "").strip().lower()
        team = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").strip().removeprefix("https://").rstrip("/")
        self.audience = os.environ.get("CF_ACCESS_AUD", "").strip()
        self.emails = {e.strip().lower() for e in os.environ.get("ADMIN_ALLOWED_EMAILS", "").split(",") if e.strip()}
        self.issuer = "https://" + team
        self.enabled = bool(re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", self.host)
                            and re.fullmatch(r"[a-z0-9-]+\.cloudflareaccess\.com", team)
                            and self.audience and self.emails)
        self.lock = threading.Lock()
        self.keys = None
        if self.enabled:
            self.keys = jwt.PyJWKClient(
                self.issuer + "/cdn-cgi/access/certs", lifespan=300, timeout=5,
                headers={"User-Agent": "LINE-Automation/1.0"},
                ssl_context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))

    def verify(self, token):
        if not self.enabled or not token or len(token) > 16384:
            raise ValueError("遠端登入尚未設定完成，或缺少登入憑證。")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise ValueError("Invalid signing header")
            with self.lock:
                key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=self.audience,
                                issuer=self.issuer, options={"require": ["exp", "iat", "iss", "aud", "sub", "email"]})
            email = claims["email"]
            if not isinstance(email, str) or email.lower() not in self.emails:
                raise ValueError("Email not allowed")
            return email.lower()
        except (jwt.PyJWTError, ValueError, TypeError, OSError) as exc:
            raise ValueError("遠端登入驗證失敗，請確認帳號或重新登入。") from exc
