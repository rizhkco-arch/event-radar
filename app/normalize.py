import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .cities import CITIES, resolve_city
from .scoring import detect_language, foreign_score, infer_category

CST = timezone(timedelta(hours=8))


@dataclass
class RawEvent:
    title: str
    description: str = ""
    start_raw: str = ""
    end_raw: str = ""
    venue: str = ""
    address: str = ""
    city: str = ""
    source: str = ""
    source_url: str = ""
    price: str = ""
    language: str = ""
    lat: float = None
    lon: float = None
    extra: dict = field(default_factory=dict)


def now_cst() -> datetime:
    return datetime.now(CST)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt.astimezone(CST).isoformat(timespec="minutes")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(CST)


DATE_PATTERNS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d",
    "%Y年%m月%d日 %H:%M",
    "%Y年%m月%d日 %H:%M:%S",
    "%Y年%m月%d日（周%w） %H:%M",
    "%Y年%m月%d日",
    "%m月%d日 %H:%M",
    "%m月%d日",
    "%m-%d %H:%M",
]


def parse_datetime(raw: str, ref: datetime = None):
    raw = (raw or "").strip()
    if not raw:
        return None
    ref = ref or now_cst()
    cleaned = raw.replace("（周日）", "").replace("（周一）", "").replace("（周二）", "").replace("（周三）", "").replace("（周四）", "").replace("（周五）", "").replace("（周六）", "")
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", cleaned).strip()
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CST)
        return dt.astimezone(CST)
    except ValueError:
        pass
    for fmt in DATE_PATTERNS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=CST)
            if "%Y" not in fmt:
                dt = dt.replace(year=ref.year, tzinfo=CST)
                if dt < ref - timedelta(days=1):
                    dt = dt.replace(year=ref.year + 1)
            return dt
        except ValueError:
            continue
    m = re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", raw)
    if m:
        mo, d, h, mi = map(int, m.groups())
        dt = ref.replace(month=mo, day=d, hour=h, minute=mi, tzinfo=CST)
        if dt < ref - timedelta(days=1):
            dt = dt.replace(year=ref.year + 1)
        return dt
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})", raw)
    if m:
        y, mo, d, h, mi = map(int, m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=CST)
    return None


VENUE_COORDS = {
    "苏州文化艺术中心": (31.3087, 120.6256),
    "suzhou culture and arts centre": (31.3087, 120.6256),
    "livehouse": None,
    "独墅湖体育馆": (31.2663, 120.7225),
}

CITY_HINTS = []
for slug, c in CITIES.items():
    CITY_HINTS.append((c["zh"], slug))
    CITY_HINTS.append((c["name"], slug))
    CITY_HINTS.append((slug, slug))


def guess_city(text: str):
    t = text or ""
    for hint, slug in CITY_HINTS:
        if hint and hint in t:
            return slug
    return None


def _norm_text(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def dedupe_key(title: str, start: datetime, venue: str) -> str:
    norm = _norm_text(title)
    s = to_iso(start)[:16] if start else ""
    v = _norm_text(venue)
    return hashlib.sha1(f"{norm}|{s}|{v}".encode("utf-8")).hexdigest()


def normalize_event(raw: RawEvent) -> dict:
    text = f"{raw.title} {raw.description} {raw.venue} {raw.address}"
    city = raw.city or guess_city(text) or "suzhou"
    lat, lon = raw.lat, raw.lon
    if lat is None or lon is None:
        c = CITIES.get(city)
        if c:
            lat, lon = c["lat"], c["lon"]
    start = parse_datetime(raw.start_raw)
    end = parse_datetime(raw.end_raw)
    if start is None:
        start = now_cst() + timedelta(hours=24)
    if end is None or (end and start and end < start):
        end = start + timedelta(hours=3)
    language = raw.language or detect_language(f"{raw.title} {raw.description}")
    category = infer_category(text)
    score, is_foreign = foreign_score(raw.title, raw.description, raw.source, language)
    return {
        "dedupe_key": dedupe_key(raw.title, start, raw.venue or raw.address),
        "title": raw.title.strip(),
        "description": (raw.description or "").strip()[:2000],
        "start_time": to_iso(start),
        "end_time": to_iso(end),
        "venue": (raw.venue or "").strip(),
        "address": (raw.address or "").strip(),
        "city": city,
        "lat": lat,
        "lon": lon,
        "category": category,
        "source": raw.source,
        "source_url": raw.source_url,
        "price": (raw.price or "").strip(),
        "language": language,
        "foreign_score": score,
        "is_foreign": 1 if is_foreign else 0,
    }
