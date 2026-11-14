import logging

from .cities import CITIES
from .db import Database
from .normalize import RawEvent, normalize_event, now_cst, to_iso
from .sources import build_sources

log = logging.getLogger("ingest")


class Ingestor:
    def __init__(self, db: Database, settings, fetcher):
        self.db = db
        self.settings = settings
        self.sources = build_sources(settings, fetcher)

    def add_manual(self, raw: RawEvent) -> tuple:
        ev = normalize_event(raw)
        return self.db.insert_event(ev)

    def run_once(self) -> list:
        """Returns list of newly inserted events (dicts)."""
        new_events = []
        for city_slug in self.settings.tracked_cities:
            c = CITIES.get(city_slug)
            if not c:
                continue
            for source in self.sources:
                started = to_iso(now_cst())
                error = None
                raws = []
                try:
                    raws = source.fetch(city_slug, c["zh"], c["lat"], c["lon"]) or []
                except Exception as e:
                    error = f"{type(e).__name__}: {e}"
                    log.exception("source %s failed for %s", source.name, city_slug)
                inserted = 0
                for raw in raws:
                    try:
                        ev = normalize_event(raw)
                        _, is_new = self.db.insert_event(ev)
                        if is_new:
                            inserted += 1
                            new_events.append(ev)
                    except Exception as e:
                        log.warning("normalize failed: %s (%s)", e, getattr(raw, "title", "?"))
                self.db.log_ingest(source.name, city_slug, started, to_iso(now_cst()), len(raws), inserted, error)
                log.info("ingest %s/%s: fetched=%d new=%d err=%s", source.name, city_slug, len(raws), inserted, error)
        return new_events

    def match_new_events(self, new_events: list) -> list:
        """[(user, event)] pairs for users whose radius covers a new event."""
        pairs = []
        for ev in new_events:
            if ev.get("lat") is None or ev.get("lon") is None:
                continue
            for user in self.db.users_matching_event(ev["lat"], ev["lon"]):
                if self.db.is_notified(user["telegram_id"], ev.get("id") or -1):
                    continue
                cats = self.db.get_cats(user)
                if cats and ev.get("category") not in cats:
                    continue
                if user.get("foreign_only") and not ev.get("is_foreign"):
                    continue
                pairs.append((user, ev))
        return pairs
