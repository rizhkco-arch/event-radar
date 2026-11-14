import json
import logging
import re
from urllib.parse import quote

from .base import RawEvent, Source

log = logging.getLogger("source.damai")


class DamaiSource(Source):
    name = "damai"

    def __init__(self, fetcher):
        self.fetcher = fetcher

    def fetch(self, city_slug, city_zh, lat, lon):
        url = f"https://search.damai.cn/search.html?city={quote(city_zh)}&keyword={quote('演出 音乐节 演唱会 脱口秀')}"
        html = self.fetcher.get(url)
        if not html:
            return []
        out = []
        for m in re.finditer(r'"itemName"\s*:\s*"((?:[^"\\]|\\.)*)"', html):
            title = m.group(1).encode().decode("unicode_escape", errors="ignore")
            out.append(title)
        events = []
        seen = set()
        for title in out:
            if title in seen:
                continue
            seen.add(title)
            events.append(RawEvent(
                title=title,
                description=title,
                city=city_slug,
                source="damai",
                source_url=url,
                lat=lat, lon=lon,
            ))
        if not events:
            log.info("damai %s: page is JS-rendered or blocked, no items parsed (skipped, not bypassed)", city_slug)
        else:
            log.info("damai %s: %d raw events", city_slug, len(events))
        return events
