import logging
import re
from urllib.parse import quote

from .base import RawEvent, Source

log = logging.getLogger("source.xiaohongshu")

KEYWORDS = ["苏州 活动", "苏州 party", "苏州 meetup", "苏州 音乐节", "苏州 展览", "苏州 英语角", "苏州 外国人 活动"]


class XiaohongshuSource(Source):
    """Best-effort public web search only.

    Xiaohongshu (Rednote) applies aggressive anti-bot protection to its web
    search. This source performs plain GET requests to public pages and only
    parses data if it is present in the HTML. It intentionally does NOT solve
    CAPTCHAs, forge signed request headers, or route through proxies to evade
    blocking. When blocked, the source simply returns nothing for the cycle
    and the radar keeps working from other sources.
    """

    name = "xiaohongshu"

    def __init__(self, fetcher, keywords=None):
        self.fetcher = fetcher
        self.keywords = keywords or KEYWORDS

    def fetch(self, city_slug, city_zh, lat, lon):
        out = []
        for kw in self.keywords:
            if city_zh and city_slug == "suzhou" and not kw.startswith(city_zh):
                kw = f"{city_zh} {kw}"
            url = f"https://www.xiaohongshu.com/search_result?keyword={quote(kw)}&type=note"
            html = self.fetcher.get(url)
            if not html:
                continue
            if "登录" in html[:3000] or "xsec" in html[:3000] or len(html) < 5000:
                log.info("xiaohongshu: anti-bot/login wall for '%s', skipping (not bypassed)", kw)
                continue
            for m in re.finditer(r'"title"\s*:\s*"((?:[^"\\]|\\.){4,120})"', html):
                title = m.group(1).encode().decode("unicode_escape", errors="ignore")
                out.append(RawEvent(
                    title=title,
                    description=kw,
                    city=city_slug,
                    source="xiaohongshu",
                    source_url=url,
                    lat=lat, lon=lon,
                ))
        log.info("xiaohongshu %s: %d raw events", city_slug, len(out))
        return out
