import logging
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

from .base import RawEvent, Source

log = logging.getLogger("source.rss")


def _text(elem, tag):
    child = elem.find(tag)
    if child is None:
        for c in elem:
            if c.tag.split("}")[-1] == tag:
                return (c.text or "").strip()
        return ""
    return (child.text or "").strip()


class RSSSource(Source):
    name = "rss"

    def __init__(self, feeds, fetcher):
        self.feeds = feeds
        self.fetcher = fetcher

    def fetch(self, city_slug, city_zh, lat, lon):
        out = []
        for url, feed_city in self.feeds:
            if feed_city and feed_city != city_slug:
                continue
            xml = self.fetcher.get(url)
            if not xml:
                continue
            try:
                root = ET.fromstring(xml)
            except ET.ParseError as e:
                log.warning("rss parse error %s: %s", url, e)
                continue
            for item in root.iter("item"):
                title = _text(item, "title")
                if not title:
                    continue
                pub = _text(item, "pubDate")
                start = ""
                if pub:
                    try:
                        dt = parsedate_to_datetime(pub)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        start = dt.isoformat()
                    except Exception:
                        start = pub
                out.append(RawEvent(
                    title=title,
                    description=_text(item, "description"),
                    start_raw=start,
                    source="rss-expat" if "expat" in url.lower() else "rss",
                    source_url=_text(item, "link") or url,
                    city=feed_city or city_slug,
                    lat=lat, lon=lon,
                ))
        return out
