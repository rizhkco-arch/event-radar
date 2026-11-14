from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from ..cities import CITIES
from .formatting import CATEGORIES, RADIUS_PRESETS


def main_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📡 Радар"), KeyboardButton("📍 Моё местоположение", request_location=True)],
         [KeyboardButton("⚙️ Настройки"), KeyboardButton("❓ Помощь")]],
        resize_keyboard=True,
    )


def radar_keyboard(radius_km: float, page: int, pages: int):
    rows = [
        [InlineKeyboardButton("➖ 10 км", callback_data="radius:-10"),
         InlineKeyboardButton(f"⭕ {radius_km:g} км", callback_data="radar:info"),
         InlineKeyboardButton("➕ 10 км", callback_data="radius:+10")],
        [InlineKeyboardButton(f"{p} км", callback_data=f"radius:{p}") for p in RADIUS_PRESETS],
    ]
    nav = []
    if pages > 1:
        if page > 1:
            nav.append(InlineKeyboardButton("⬅️", callback_data=f"radar:page:{page-1}"))
        nav.append(InlineKeyboardButton(f"{page}/{pages}", callback_data="radar:info"))
        if page < pages:
            nav.append(InlineKeyboardButton("➡️", callback_data=f"radar:page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔄 Обновить", callback_data="radar:page:1"),
                 InlineKeyboardButton("🌆 Город", callback_data="city:list"),
                 InlineKeyboardButton("⚙️", callback_data="settings")])
    return InlineKeyboardMarkup(rows)


def city_keyboard():
    rows = []
    row = []
    for slug in CITIES:
        c = CITIES[slug]
        row.append(InlineKeyboardButton(f"{c['name']}", callback_data=f"city:{slug}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("📍 По геолокации", callback_data="city:loc")])
    return InlineKeyboardMarkup(rows)


def settings_keyboard(user: dict):
    foreign = "✅" if user.get("foreign_only") else "❌"
    notify = "✅" if user.get("notify") else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🌍 Только иностранные: {foreign}", callback_data="set:foreign:toggle"),
         InlineKeyboardButton(f"🔔 Уведомления: {notify}", callback_data="set:notify:toggle")],
        [InlineKeyboardButton("🏷 Категории…", callback_data="cats")],
        [InlineKeyboardButton(f"⭕ Радиус: {user.get('radius_km'):g} км", callback_data="radar:info")],
        [InlineKeyboardButton("🔙 К радару", callback_data="radar:page:1")],
    ])


def cats_keyboard(selected: list):
    rows = []
    row = []
    for cat in CATEGORIES:
        mark = "✅" if not selected or cat in selected else "▫️"
        row.append(InlineKeyboardButton(f"{mark} {cat}", callback_data=f"cat:{cat}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("Сбросить (все)", callback_data="cat:all"),
                 InlineKeyboardButton("🔙 Назад", callback_data="settings")])
    return InlineKeyboardMarkup(rows)
