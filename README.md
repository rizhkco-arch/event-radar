# 📡 China Events Radar Bot

Telegram-бот-радар мероприятий в Китае. Центр по умолчанию — **Сучжоу**, радиус расширяется и сужается кнопками прямо в чате. Ищет ивенты «всех порядков» — иностранные в приоритете (🌍-бейдж и фильтр), китайские с иностранным уклоном тоже попадают.

## Быстрый старт

```bash
cp .env.example .env          # вставь BOT_TOKEN от @BotFather и свой ID в ADMIN_IDS
docker compose up -d --build   # или локально:
# pip install -r requirements.txt && python -m app.main
```

Проверить сбор источников без Telegram:

```bash
python -m app.main --ingest-once
```

Тесты:

```bash
python -m unittest discover -s tests -v
```

## Команды бота

| Команда | Что делает |
|---|---|
| `/start` | онбординг, выбор центра (кнопки городов или 📍 геолокация) |
| `/radar` | список ивентов в радиусе + кнопки ➖10/➕10 км и пресеты 5–300 км |
| `/radius 50` | радиус напрямую, км |
| `/city` / `/city 上海` | сменить город-центр |
| `/today` `/weekend` `/week` | срезы по времени в текущем радиусе |
| `/foreign on\|off` | показывать только ивенты для иностранцев (score ≥ 50) |
| `/notify on\|off` | уведомления о новых ивентах в твоём радиусе |
| `/cat` | фильтр категорий |
| `/add Название \| 2025-05-24 20:00 \| место \| ссылка` | ручное добавление ивента |
| `/saved` | избранное |
| `/stats` `/ingest` | админ (ID из `ADMIN_IDS`) |

## Как устроен радар

- Центр = город из `app/cities.py` или твоя геолокация; радиус хранится у каждого юзера и меняется кнопками — это просто параметр запроса.
- Гео:haversine в `app/geo.py`, préfilter по bounding-box в SQL, точный фильтр по расстоянию — радиус сужается/расширяется мгновенно.
- Каждый ивент получает `foreign_score` (0–100): + за маркеры expat/international/English/языковой обмен/meetup и англоязычность, + за источник Meetup/Eventbrite/палаты, − за чисто локальные маркеры (相亲, 本地…). `is_foreign = score ≥ 50`.
- Категория определяется по ключевым словам (en+zh): music, art, tech, food, sport, family, nightlife, business, education, travel.
- Дедупликация: `sha1(title|дата|место)` — один ивент из разных источников считается один раз.

## Источники (`app/sources/`)

- **douban** — публичные страницы `douban.com/location/<город>/events/` (инди, выставки, лекции, языковые обмены);
- **damai** — публичный поиск 大麦 (концерты, фестивали, стендап);
- **xiaohongshu (Rednote)** — только обычные GET-запросы к публичным страницам поиска. **Антибот-защита не обходится**: никаких капч, подделки подписей, прокси-ротации. Если Rednote отвечает стеной логина/403 — источник просто пропускает цикл, радар работает по остальным;
- **meetup** — GraphQL API при наличии `MEETUP_TOKEN`;
- **rss** — произвольные RSS-ленты через `RSS_FEEDS=url|город;…`;
- **manual** — команда `/add`.

Все HTTP-запросы идут через `app/http.py` с per-host rate-limit и таймаутами; при блокировке источник логируется и пропускается, бот не падает. Сбор запускается планировщиком каждые `INGEST_INTERVAL_MIN` минут, новые ивенты рассылаются подписчикам, чей радиус их покрывает (с защитой от дублей и тихими часами `QUIET_START`/`QUIET_END` по времени Китая).

## Структура

```
app/
├── config.py        # настройки из .env
├── cities.py        # города дельты Янцзы + Пекин/Шэньчжэнь… с координатами
├── geo.py           # haversine, bounding box, фильтр по радиусу
├── scoring.py       # foreign_score, категории, язык
├── normalize.py     # RawEvent -> Event, парсинг дат (в т.ч. «2025年5月24日 19:30»), дедуп
├── db.py            # SQLite: users, events, saved, notified, ingest_log
├── http.py          # вежливый fetcher (rate-limit, без обхода защит)
├── ingest.py        # цикл сбора + сопоставление с радиусами юзеров
├── sources/         # douban, damai, xiaohongshu, meetup, rss (+base)
├── bot/             # handlers.py (команды), keyboards.py, formatting.py
└── main.py          # entrypoint: polling + планировщик
tests/               # unittest: geo, scoring, normalize, db
docker-compose.yml, Dockerfile, .env.example
```

## Дальше

- Перейти с SQLite на PostgreSQL+PostGIS (`ST_DWithin`) при росте — интерфейс `db.py` не меняется;
- словарь площадок Сучжоу/Шанхая с точными координатами вместо центра города;
- кэш превью и мультиязычные карточки (en/ru/zh).
