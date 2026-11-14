import argparse
import asyncio
import logging
from datetime import datetime

from .bot.formatting import event_card
from .bot.handlers import BotHandlers
from .config import Settings
from .db import Database
from .geo import haversine_km
from .http import Fetcher
from .ingest import Ingestor
from .normalize import CST, now_cst

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("main")


def in_quiet_hours(settings) -> bool:
    h = now_cst().hour
    if settings.quiet_start <= settings.quiet_end:
        return settings.quiet_start <= h < settings.quiet_end
    return h >= settings.quiet_start or h < settings.quiet_end


async def notify_new_events(app, db: Database, settings, ingestor: Ingestor):
    try:
        new_events = await asyncio.to_thread(ingestor.run_once)
    except Exception:
        log.exception("ingest cycle failed")
        return
    if not new_events:
        return
    if in_quiet_hours(settings):
        log.info("quiet hours, %d new events kept for later", len(new_events))
        return
    sent = 0
    for user, ev in ingestor.match_new_events(new_events):
        if sent >= settings.max_notify_per_cycle * 20:
            break
        event_row = None
        try:
            with db._conn() as con:
                row = con.execute("SELECT * FROM events WHERE dedupe_key=?", (ev["dedupe_key"],)).fetchone()
                event_row = dict(row) if row else None
        except Exception:
            pass
        if not event_row:
            continue
        if db.is_notified(user["telegram_id"], event_row["id"]):
            continue
        dist = haversine_km(user["lat"], user["lon"], event_row["lat"], event_row["lon"])
        text = "🔔 <b>Новое в твоём радиусе!</b>\n\n" + event_card(event_row, dist)
        try:
            await app.bot.send_message(user["telegram_id"], text, parse_mode="HTML")
            db.mark_notified(user["telegram_id"], event_row["id"])
            sent += 1
        except Exception as e:
            log.warning("notify to %s failed: %s", user["telegram_id"], e)
    log.info("notified %d users about new events", sent)


def run_ingest_once(settings: Settings):
    db = Database(settings.db_path)
    fetcher = Fetcher(settings.user_agent, settings.request_timeout, settings.min_request_interval_sec)
    ingestor = Ingestor(db, settings, fetcher)
    new = ingestor.run_once()
    print(f"ingest done: {len(new)} new events")
    return new


def run_bot(settings: Settings):
    from telegram.ext import Application

    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is empty. Put it into .env (see .env.example).")
    db = Database(settings.db_path)
    fetcher = Fetcher(settings.user_agent, settings.request_timeout, settings.min_request_interval_sec)
    ingestor = Ingestor(db, settings, fetcher)
    handlers = BotHandlers(db, settings, ingestor)

    app = Application.builder().token(settings.bot_token).build()
    handlers.register(app)

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        notify_new_events,
        "interval",
        minutes=settings.ingest_interval_min,
        args=[app, db, settings, ingestor],
        id="ingest",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(notify_new_events, "date", run_date=datetime.now(CST), args=[app, db, settings, ingestor], id="ingest_startup")
    scheduler.start()
    log.info("bot started, ingest every %d min", settings.ingest_interval_min)
    app.run_polling(allowed_updates=["message", "callback_query"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest-once", action="store_true", help="run one ingest cycle and exit (no Telegram needed)")
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()
    settings = Settings.from_env(args.env)
    logging.getLogger().setLevel(settings.log_level)
    if args.ingest_once:
        run_ingest_once(settings)
    else:
        run_bot(settings)


if __name__ == "__main__":
    main()
