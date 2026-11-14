import logging

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from ..cities import CITIES, nearest_city_slug, resolve_city
from ..db import Database
from ..geo import haversine_km
from ..ingest import Ingestor
from ..normalize import RawEvent, now_cst, parse_datetime, to_iso
from .formatting import CATEGORIES, city_label, event_card, radar_text
from .keyboards import cats_keyboard, city_keyboard, main_menu, radar_keyboard, settings_keyboard

log = logging.getLogger("bot")


class BotHandlers:
    def __init__(self, db: Database, settings, ingestor: Ingestor = None):
        self.db = db
        self.settings = settings
        self.ingestor = ingestor

    def _user(self, update: Update):
        u = update.effective_user
        self.db.upsert_user(u.id, u.username, u.first_name)
        return self.db.get_user(u.id)

    def _is_admin(self, update: Update) -> bool:
        return update.effective_user.id in self.settings.admin_ids

    def register(self, app):
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help))
        app.add_handler(CommandHandler("radar", self.radar))
        app.add_handler(CommandHandler("radius", self.radius))
        app.add_handler(CommandHandler("city", self.city))
        app.add_handler(CommandHandler("today", lambda u, c: self.time_view(u, c, "today")))
        app.add_handler(CommandHandler("weekend", lambda u, c: self.time_view(u, c, "weekend")))
        app.add_handler(CommandHandler("week", lambda u, c: self.time_view(u, c, "week")))
        app.add_handler(CommandHandler("cat", self.cat))
        app.add_handler(CommandHandler("foreign", self.foreign))
        app.add_handler(CommandHandler("notify", self.notify))
        app.add_handler(CommandHandler("saved", self.saved))
        app.add_handler(CommandHandler("add", self.add))
        app.add_handler(CommandHandler("settings", self.settings_cmd))
        app.add_handler(CommandHandler("stats", self.stats))
        app.add_handler(CommandHandler("ingest", self.ingest_now))
        app.add_handler(MessageHandler(filters.LOCATION, self.on_location))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))
        app.add_handler(CallbackQueryHandler(self.on_callback))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        text = (
            f"Привет, {update.effective_user.first_name or ''}! 👋\n\n"
            f"Я радар мероприятий по Китаю. Сейчас центр: <b>{city_label(user.get('city'))}</b>, "
            f"радиус <b>{user.get('radius_km'):g} км</b>.\n\n"
            "Выбери центр радара (или отправь геолокацию 📍), потом смотри /radar и крути радиус кнопками."
        )
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())
        await update.message.reply_text("Центр радара:", reply_markup=city_keyboard())

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📡 <b>Радар</b>\n"
            "/radar — ивенты в твоём радиусе (кнопки ➕/➖ меняют радиус)\n"
            "/radius 50 — установить радиус в км\n"
            "/city — сменить город-центр (Сучжоу, Шанхай, Ханчжоу…)\n"
            "/today /weekend /week — срезы по времени в текущем радиусе\n\n"
            "⚙️ <b>Настройки</b>\n"
            "/foreign on|off — только ивенты для иностранцев 🌍\n"
            "/notify on|off — уведомления о новых ивентах в радиусе\n"
            "/cat — фильтр по категориям\n"
            "/settings — все настройки сразу\n\n"
            "➕ <b>Другое</b>\n"
            "/add Название | 2025-05-24 20:00 | место, адрес | ссылка — добавить ивент вручную\n"
            "/saved — избранное\n"
            "/stats, /ingest — админ-команды",
            parse_mode="HTML",
        )

    def _radar_events(self, user, time_filter=None, page_size=None):
        from datetime import timedelta
        after = now_cst()
        if time_filter == "today":
            after = now_cst().replace(hour=0, minute=0)
        elif time_filter == "week":
            after = now_cst() - timedelta(days=0)
        elif time_filter == "weekend":
            after = now_cst()
        limit = 100
        evs = self.db.events_in_radius(
            user["lat"], user["lon"], user["radius_km"],
            after=after, limit=limit,
            categories=self.db.get_cats(user) or None,
            foreign_only=bool(user.get("foreign_only")),
        )
        if time_filter == "today":
            end = now_cst().replace(hour=0, minute=0) + timedelta(days=1)
            evs = [e for e in evs if e["start_time"] < to_iso(end)]
        elif time_filter == "week":
            end = now_cst() + timedelta(days=7)
            evs = [e for e in evs if parse_iso_(e["start_time"]) < end]
        elif time_filter == "weekend":
            from ..normalize import parse_iso
            now = now_cst()
            days_ahead = (4 - now.weekday()) % 7
            sat = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0)
            sun_end = sat + timedelta(days=2)
            evs = [e for e in evs if sat <= parse_iso(e["start_time"]) < sun_end]
        return evs

    async def radar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        evs = self._radar_events(user, page_size=self.settings.radar_page_size)
        page = 1
        pages = max(1, (len(evs) + self.settings.radar_page_size - 1) // self.settings.radar_page_size)
        text = radar_text(user, evs, page, self.settings.radar_page_size)
        if update.message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=radar_keyboard(user["radius_km"], page, pages))

    async def time_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str):
        user = self._user(update)
        evs = self._radar_events(user, time_filter=kind)
        names = {"today": "Сегодня", "weekend": "Эти выходные", "week": "Ближайшая неделя"}
        header = f"🗓 <b>{names[kind]}</b> · {city_label(user.get('city'))} · радиус {user.get('radius_km'):g} км"
        if not evs:
            body = "Пусто. Попробуй расширить радиус (/radius 100)."
        else:
            body = "\n\n".join(event_card(e, e.get("distance_km"), i + 1) for i, e in enumerate(evs[:15]))
        await update.message.reply_text(header + "\n\n" + body, parse_mode="HTML", reply_markup=radar_keyboard(user["radius_km"], 1, 1))

    async def radius(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        args = context.args
        if args and args[0].replace(".", "", 1).isdigit():
            r = float(args[0])
            r = max(1, min(1000, r))
            self.db.update_user(user["telegram_id"], radius_km=r)
            await update.message.reply_text(f"⭕ Радиус установлен: <b>{r:g} км</b>", parse_mode="HTML")
            await self.radar(update, context)
        else:
            await update.message.reply_text(
                f"Текущий радиус: <b>{user['radius_km']:g} км</b>.\nИспользуй /radius 50 или кнопки в /radar.",
                parse_mode="HTML",
                reply_markup=radar_keyboard(user["radius_km"], 1, 1),
            )

    async def city(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        args = context.args
        if args:
            slug = resolve_city(" ".join(args))
            if not slug:
                await update.message.reply_text("Не знаю такого города. Список: /city")
                return
            c = CITIES[slug]
            self.db.update_user(user["telegram_id"], city=slug, lat=c["lat"], lon=c["lon"])
            await update.message.reply_text(f"🌆 Центр радара: <b>{city_label(slug)}</b>", parse_mode="HTML")
            await self.radar(update, context)
        else:
            await update.message.reply_text("Выбери город-центр:", reply_markup=city_keyboard())

    async def cat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        await update.message.reply_text("Выбери категории (✅ = включены, пустой список = все):",
                                        reply_markup=cats_keyboard(self.db.get_cats(user)))

    async def foreign(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        val = 1 if (context.args and context.args[0].lower() in ("on", "1", "yes", "да")) else 0
        if not context.args:
            val = 0 if user.get("foreign_only") else 1
        self.db.update_user(user["telegram_id"], foreign_only=val)
        await update.message.reply_text(f"🌍 Только иностранные ивенты: <b>{'вкл' if val else 'выкл'}</b>", parse_mode="HTML")

    async def notify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        val = 1 if (context.args and context.args[0].lower() in ("on", "1", "yes", "да")) else 0
        if not context.args:
            val = 0 if user.get("notify") else 1
        self.db.update_user(user["telegram_id"], notify=val)
        await update.message.reply_text(f"🔔 Уведомления: <b>{'вкл' if val else 'выкл'}</b>", parse_mode="HTML")

    async def saved(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        evs = self.db.saved_events(user["telegram_id"])
        if not evs:
            await update.message.reply_text("Избранное пусто.")
            return
        body = "\n\n".join(event_card(e, haversine_km(user["lat"], user["lon"], e["lat"], e["lon"]) if e["lat"] else None, i + 1) for i, e in enumerate(evs[:15]))
        await update.message.reply_text("⭐ <b>Избранное</b>\n\n" + body, parse_mode="HTML")

    async def add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        text = " ".join(context.args) if context.args else ""
        if not text or "|" not in text:
            await update.message.reply_text(
                "Формат: /add Название | 2025-05-24 20:00 | место, адрес | ссылка\n"
                "Пример: /add Jazz Night | 2025-05-24 20:00 | 苏州文化艺术中心 | https://…"
            )
            return
        parts = [p.strip() for p in text.split("|")]
        title = parts[0]
        start_raw = parts[1] if len(parts) > 1 else ""
        addr = parts[2] if len(parts) > 2 else ""
        url = parts[3] if len(parts) > 3 else ""
        raw = RawEvent(title=title, start_raw=start_raw, address=addr, city=user.get("city") or "suzhou",
                       source="manual", source_url=url, lat=user.get("lat"), lon=user.get("lon"))
        if self.ingestor:
            event_id, _ = self.ingestor.add_manual(raw)
        else:
            from ..normalize import normalize_event
            ev = normalize_event(raw)
            event_id, _ = self.db.insert_event(ev)
        ev = self.db.get_event(event_id)
        await update.message.reply_text("✅ Добавлено:\n\n" + event_card(ev), parse_mode="HTML")

    async def settings_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = self._user(update)
        cats = self.db.get_cats(user)
        text = (
            "⚙️ <b>Настройки</b>\n"
            f"🌆 Центр: {city_label(user.get('city'))}\n"
            f"⭕ Радиус: {user.get('radius_km'):g} км\n"
            f"🌍 Только иностранные: {'да' if user.get('foreign_only') else 'нет'}\n"
            f"🔔 Уведомления: {'вкл' if user.get('notify') else 'выкл'}\n"
            f"🏷 Категории: {', '.join(cats) if cats else 'все'}"
        )
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=settings_keyboard(user))

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        s = self.db.stats()
        logs = self.db.recent_logs(8)
        lines = [f"👥 users: {s['users']}", f"📅 всего ивентов: {s['events']} (будущих: {s['future_events']}, 🌍: {s['foreign_events']})", "", "Последние запуски источников:"]
        for l in logs:
            lines.append(f"• {l['source']}/{l['city']}: fetched={l['fetched']} new={l['inserted']}" + (f" ⚠️ {l['error']}" if l['error'] else ""))
        await update.message.reply_text("\n".join(lines))

    async def ingest_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update):
            return
        if not self.ingestor:
            await update.message.reply_text("Ingestor не инициализирован.")
            return
        await update.message.reply_text("🔄 Запускаю сбор…")
        new = self.ingestor.run_once()
        await update.message.reply_text(f"Готово: новых ивентов {len(new)}.")

    async def on_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        loc = update.message.location
        slug = nearest_city_slug(loc.latitude, loc.longitude)
        self.db.upsert_user(update.effective_user.id, lat=loc.latitude, lon=loc.longitude, city=slug)
        await update.message.reply_text(
            f"📍 Центр радара: <b>{city_label(slug)}</b> ({loc.latitude:.4f}, {loc.longitude:.4f})",
            parse_mode="HTML",
        )
        await self.radar(update, context)

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        t = (update.message.text or "").strip()
        mapping = {"📡 радар": "/radar", "❓ помощь": "/help", "⚙️ настройки": "/settings", "📍 моё местоположение": "отправь геолокацию кнопкой 📍"}
        if t.lower() in mapping:
            await update.message.reply_text(f"Используй команду {mapping[t.lower()]}")
        else:
            await update.message.reply_text("Команды: /help")

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        user = self._user(update)
        data = q.data or ""
        await q.answer()
        if data.startswith("radius:"):
            arg = data.split(":", 1)[1]
            if arg in ("+10", "-10"):
                delta = 10 if arg == "+10" else -10
                r = max(1, min(1000, user["radius_km"] + delta))
            else:
                r = float(arg)
            self.db.update_user(user["telegram_id"], radius_km=r)
            user = self.db.get_user(user["telegram_id"])
            evs = self._radar_events(user)
            pages = max(1, (len(evs) + self.settings.radar_page_size - 1) // self.settings.radar_page_size)
            await q.edit_message_text(radar_text(user, evs, 1, self.settings.radar_page_size),
                                      parse_mode="HTML", reply_markup=radar_keyboard(r, 1, pages))
        elif data.startswith("radar:page:"):
            page = int(data.split(":")[-1])
            evs = self._radar_events(user)
            pages = max(1, (len(evs) + self.settings.radar_page_size - 1) // self.settings.radar_page_size)
            await q.edit_message_text(radar_text(user, evs, page, self.settings.radar_page_size),
                                      parse_mode="HTML", reply_markup=radar_keyboard(user["radius_km"], page, pages))
        elif data == "radar:info":
            pass
        elif data == "city:list":
            await q.edit_message_text("Выбери город-центр:", reply_markup=city_keyboard())
        elif data == "city:loc":
            await q.edit_message_text("Отправь геолокацию кнопкой 📍 на клавиатуре внизу.")
        elif data.startswith("city:"):
            slug = data.split(":", 1)[1]
            c = CITIES.get(slug)
            if c:
                self.db.update_user(user["telegram_id"], city=slug, lat=c["lat"], lon=c["lon"])
                user = self.db.get_user(user["telegram_id"])
                evs = self._radar_events(user)
                pages = max(1, (len(evs) + self.settings.radar_page_size - 1) // self.settings.radar_page_size)
                await q.edit_message_text(radar_text(user, evs, 1, self.settings.radar_page_size),
                                          parse_mode="HTML", reply_markup=radar_keyboard(user["radius_km"], 1, pages))
        elif data == "settings":
            cats = self.db.get_cats(user)
            text = (f"⚙️ Центр: {city_label(user.get('city'))} · ⭕ {user.get('radius_km'):g} км\n"
                    f"🌍 только иностранные: {'да' if user.get('foreign_only') else 'нет'} · 🔔 уведомления: {'вкл' if user.get('notify') else 'выкл'}\n"
                    f"🏷 категории: {', '.join(cats) if cats else 'все'}")
            await q.edit_message_text(text, parse_mode="HTML", reply_markup=settings_keyboard(user))
        elif data == "cats":
            await q.edit_message_text("Категории:", reply_markup=cats_keyboard(self.db.get_cats(user)))
        elif data == "cat:all":
            self.db.set_cats(user["telegram_id"], [])
            await q.edit_message_text("Категории: все", reply_markup=cats_keyboard([]))
        elif data.startswith("cat:"):
            cat = data.split(":", 1)[1]
            cats = self.db.get_cats(user)
            if cat in cats:
                cats.remove(cat)
            else:
                cats.append(cat)
            self.db.set_cats(user["telegram_id"], cats)
            await q.edit_message_text("Категории:", reply_markup=cats_keyboard(cats))
        elif data == "set:foreign:toggle":
            self.db.update_user(user["telegram_id"], foreign_only=0 if user.get("foreign_only") else 1)
            user = self.db.get_user(user["telegram_id"])
            await q.edit_message_text("⚙️ Настройки", reply_markup=settings_keyboard(user))
        elif data == "set:notify:toggle":
            self.db.update_user(user["telegram_id"], notify=0 if user.get("notify") else 1)
            user = self.db.get_user(user["telegram_id"])
            await q.edit_message_text("⚙️ Настройки", reply_markup=settings_keyboard(user))


def parse_iso_(iso: str):
    from ..normalize import parse_iso
    return parse_iso(iso)
