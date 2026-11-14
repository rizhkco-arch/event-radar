import os
from dataclasses import dataclass, field
from pathlib import Path


def load_env_file(path: str) -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    bot_token: str = ""
    db_path: str = "data/bot.db"
    default_city: str = "suzhou"
    default_radius_km: float = 30.0
    ingest_interval_min: int = 30
    tracked_cities: list = field(default_factory=lambda: ["suzhou", "shanghai", "hangzhou", "wuxi", "nanjing"])
    admin_ids: set = field(default_factory=set)
    request_timeout: int = 15
    min_request_interval_sec: float = 4.0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    max_notify_per_cycle: int = 10
    radar_page_size: int = 8
    quiet_start: int = 22
    quiet_end: int = 8
    meetup_token: str = ""
    rss_feeds: list = field(default_factory=list)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "Settings":
        load_env_file(env_file)
        admins = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()}
        cities = [c.strip() for c in os.environ.get("TRACKED_CITIES", "suzhou,shanghai,hangzhou,wuxi,nanjing").split(",") if c.strip()]
        feeds = []
        raw_feeds = os.environ.get("RSS_FEEDS", "")
        for item in raw_feeds.split(";"):
            if "|" in item:
                url, city = item.split("|", 1)
                feeds.append((url.strip(), city.strip()))
        return cls(
            bot_token=os.environ.get("BOT_TOKEN", ""),
            db_path=os.environ.get("DB_PATH", "data/bot.db"),
            default_city=os.environ.get("DEFAULT_CITY", "suzhou"),
            default_radius_km=float(os.environ.get("DEFAULT_RADIUS_KM", "30")),
            ingest_interval_min=int(os.environ.get("INGEST_INTERVAL_MIN", "30")),
            tracked_cities=cities,
            admin_ids=admins,
            request_timeout=int(os.environ.get("REQUEST_TIMEOUT", "15")),
            min_request_interval_sec=float(os.environ.get("MIN_REQUEST_INTERVAL_SEC", "4")),
            user_agent=os.environ.get("USER_AGENT", cls.user_agent),
            max_notify_per_cycle=int(os.environ.get("MAX_NOTIFY_PER_CYCLE", "10")),
            radar_page_size=int(os.environ.get("RADAR_PAGE_SIZE", "8")),
            quiet_start=int(os.environ.get("QUIET_START", "22")),
            quiet_end=int(os.environ.get("QUIET_END", "8")),
            meetup_token=os.environ.get("MEETUP_TOKEN", ""),
            rss_feeds=feeds,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
