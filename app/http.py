import logging
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

log = logging.getLogger("http")


class Fetcher:
    """Polite HTTP GET with per-host rate limiting.

    Deliberately does NOT bypass anti-bot measures: no CAPTCHA solving,
    no request-signing forgery, no proxy rotation. If a site returns
    403/418/login-wall, the source is skipped for this cycle.
    """

    def __init__(self, user_agent: str, timeout: int = 15, min_interval: float = 4.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self._last: dict = {}
        self._lock = threading.Lock()

    def _wait(self, host: str):
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            delay = self.min_interval - (now - last)
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.monotonic()

    def get(self, url: str, extra_headers: dict = None):
        host = urlparse(url).netloc
        self._wait(host)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", **(extra_headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    log.warning("GET %s -> %s", url, resp.status)
                    return None
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read(200_000).decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            log.warning("GET %s -> HTTP %s (skipped, not bypassed)", url, e.code)
            return None
        except Exception as e:
            log.warning("GET %s failed: %s", url, e)
            return None

    def post_json(self, url: str, payload: dict, headers: dict = None):
        import json as _json
        host = urlparse(url).netloc
        self._wait(host)
        body = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"User-Agent": self.user_agent, "Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return _json.loads(resp.read(200_000).decode(charset, errors="replace"))
        except Exception as e:
            log.warning("POST %s failed: %s", url, e)
            return None
