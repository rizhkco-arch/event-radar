import logging
import re
from urllib.parse import quote

from .base import RawEvent, Source

log = logging.getLogger("source.douban")

ITEM_RE = re.compile(r'<li class="item">(.*?)</li>', re.S)
ANCHOR_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]+)"', re.S)
ANCHOR_RE2 = re.compile(r'<a[^>]+title="([^"]+)"[^>]+href="([^"]+)"', re.S)
DATE_RE = re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日[^<]{0,20}|\d{4}-\d{2}-\d{2}[^<]{0,20}|\d{1,2}月\d{1,2}日[^<]{0,20})")
ADDR_RE = re.compile(r"([\w一-鿿]{2,20}(?:路|街|号|中心|广场|艺术中心|体育馆|剧院|馆|园)[\w一-鿿\d号-]{0,30})")
PRICE_RE = re.compile(r"(\d+\s*[-~—]\s*\d+\s*元|免费|free)", re.I)


def _clean(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _attr(html: str, name: str):
    m = re.search(name + r'="([^"]*)"', html)
    return m.group(1) if m else ""


class DoubanSource(Source):
    name = "douban"

    def __init__(self, fetcher):
        self.fetcher = fetcher

    def fetch(self, city_slug, city_zh, lat, lon):
        url = f"https://www.douban.com/location/{quote(city_slug)}/events/week-all"
        html = self.fetcher.get(url)
        if not html:
            return []
        if "登录" in html and "events" not in html[:2000] and len(html) < 20000:
            log.info("douban %s: login wall, skipping this cycle", city_slug)
            return []
        out = []
        for block in ITEM_RE.findall(html):
            anchors = ANCHOR_RE.findall(block) or ANCHOR_RE2.findall(block)
            if not anchors:
                anchors = [(m.group(2), m.group(1)) for m in re.finditer(r'<a[^>]+href="(https://www\.douban\.com/event/\d+/[^"]*)"[^>]*>([^<]{2,80})</a>', block)]
                anchors = [(h, t) for h, t in anchors]
            if not anchors:
                continue
            href, title = anchors[0]
            if not title.strip():
                continue
            text = _clean(block)
            dm = DATE_RE.search(text)
            start_raw = dm.group(1) if dm else ""
            am = ADDR_RE.search(text)
            addr = am.group(1) if am else ""
            pm = PRICE_RE.search(text)
            price = pm.group(1) if pm else ""
            out.append(RawEvent(
                title=title.strip(),
                description=text[:500],
                start_raw=start_raw,
                venue="",
                address=addr,
                city=city_slug,
                source="douban",
                source_url=href if href.startswith("http") else "https://www.douban.com" + href,
                price=price,
                lat=lat, lon=lon,
            ))
        log.info("douban %s: %d raw events", city_slug, len(out))
        return out
