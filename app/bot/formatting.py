from datetime import datetime

from ..cities import CITIES
from ..normalize import CST, parse_iso

CATEGORY_EMOJI = {
    "music": "🎵", "art": "🎨", "tech": "💻", "food": "🍜", "sport": "🏃",
    "family": "👨‍👩‍👧", "nightlife": "🍸", "business": "💼", "education": "📚",
    "travel": "🧭", "other": "📌",
}

RADIUS_PRESETS = [5, 15, 30, 50, 100, 200, 300]

CATEGORIES = ["music", "art", "tech", "food", "sport", "family", "nightlife", "business", "education", "travel"]


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_dt(iso: str) -> str:
    try:
        dt = parse_iso(iso)
        return dt.strftime("%d.%m %H:%M")
    except Exception:
        return iso or "?"


def event_card(ev: dict, dist_km: float = None, index: int = None) -> str:
    emoji = CATEGORY_EMOJI.get(ev.get("category"), "📌")
    badge = " 🌍 expat" if ev.get("is_foreign") else ""
    lang = f" · 🗣 {ev.get('language')}" if ev.get("language") and ev.get("language") != "unknown" else ""
    price = f" · 💰 {esc(ev['price'])}" if ev.get("price") else ""
    lines = []
    prefix = f"{index}. " if index else ""
    lines.append(f"{prefix}{emoji} <b>{esc(ev['title'])}</b>{badge}")
    lines.append(f"   🗓 {fmt_dt(ev['start_time'])}"
                 + (f" → {fmt_dt(ev['end_time'])}" if ev.get("end_time") else "")
                 + f" · 📍 {esc(ev.get('venue') or ev.get('address') or ev.get('city') or '')}"
                 + (f" · {dist_km:.1f} км" if dist_km is not None else "")
                 + lang + price)
    if ev.get("source_url"):
        lines.append(f"   🔗 <a href=\"{esc(ev['source_url'])}\">источник ({esc(ev.get('source') or '?')})</a>")
    return "\n".join(lines)


def city_label(slug: str) -> str:
    c = CITIES.get(slug)
    return f"{c['name']} {c['zh']}" if c else slug


def radar_text(user: dict, events: list, page: int, page_size: int) -> str:
    total = len(events)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(page, 1), pages)
    chunk = events[(page - 1) * page_size: page * page_size]
    header = (f"📡 <b>Радар</b> — центр: <b>{esc(city_label(user.get('city')))}</b>"
              f" ({user.get('lat'):.4f}, {user.get('lon'):.4f})\n"
              f"Радиус: <b>{user.get('radius_km')} км</b> · найдено ивентов: <b>{total}</b>"
              + (f" · стр. {page}/{pages}" if pages > 1 else ""))
    if not chunk:
        return header + "\n\nВ этом радиусе пока пусто. Расширь радиус кнопками ниже 👇"
    body = "\n\n".join(event_card(e, e.get("distance_km"), i + (page - 1) * page_size + 1) for i, e in enumerate(chunk))
    return header + "\n\n" + body
