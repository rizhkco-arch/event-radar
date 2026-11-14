import math

CITIES = {
    "suzhou": {"name": "Сучжоу", "zh": "苏州", "lat": 31.2989, "lon": 120.5853, "province": "Цзянсу"},
    "shanghai": {"name": "Шанхай", "zh": "上海", "lat": 31.2304, "lon": 121.4737, "province": "Шанхай"},
    "hangzhou": {"name": "Ханчжоу", "zh": "杭州", "lat": 30.2741, "lon": 120.1551, "province": "Чжэцзян"},
    "nanjing": {"name": "Нанкин", "zh": "南京", "lat": 32.0603, "lon": 118.7969, "province": "Цзянсу"},
    "wuxi": {"name": "Уси", "zh": "无锡", "lat": 31.4912, "lon": 120.3119, "province": "Цзянсу"},
    "kunshan": {"name": "Куньшань", "zh": "昆山", "lat": 31.3989, "lon": 120.9545, "province": "Цзянсу"},
    "nantong": {"name": "Наньтун", "zh": "南通", "lat": 32.0162, "lon": 120.8943, "province": "Цзянсу"},
    "yangzhou": {"name": "Янчжоу", "zh": "扬州", "lat": 32.3943, "lon": 119.4127, "province": "Цзянсу"},
    "beijing": {"name": "Пекин", "zh": "北京", "lat": 39.9042, "lon": 116.4074, "province": "Пекин"},
    "shenzhen": {"name": "Шэньчжэнь", "zh": "深圳", "lat": 22.5431, "lon": 114.0579, "province": "Гуандун"},
    "guangzhou": {"name": "Гуанчжоу", "zh": "广州", "lat": 23.1291, "lon": 113.2644, "province": "Гуандун"},
    "chengdu": {"name": "Чэнду", "zh": "成都", "lat": 30.5728, "lon": 104.0668, "province": "Сычуань"},
    "xian": {"name": "Сиань", "zh": "西安", "lat": 34.3416, "lon": 108.9398, "province": "Шэньси"},
}

ALIASES = {}
for slug, c in CITIES.items():
    ALIASES[slug] = slug
    ALIASES[c["name"].lower()] = slug
    ALIASES[c["zh"]] = slug
    ALIASES[c["name"].lower().replace("ё", "е")] = slug


def resolve_city(query: str):
    if not query:
        return None
    q = query.strip().lower()
    if q in ALIASES:
        return ALIASES[q]
    for slug, c in CITIES.items():
        if q in c["name"].lower() or q in c["zh"]:
            return slug
    return None


def nearest_city_slug(lat: float, lon: float):
    best, best_d = None, float("inf")
    for slug, c in CITIES.items():
        d = math.hypot(lat - c["lat"], lon - c["lon"])
        if d < best_d:
            best, best_d = slug, d
    return best


def get_city(slug: str):
    return CITIES.get(slug)
