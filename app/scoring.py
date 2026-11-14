import re

FOREIGN_KEYWORDS = [
    "international", "expat", "expat-friendly", "foreigner", "foreign", "english",
    "language exchange", "meetup", "open mic", "board game", "boardgame", "hiking",
    "jazz", "craft beer", "trivia", "stand-up", "standup", "comedy night", "yoga",
    "climbing", "bouldering", "hackathon", "startup", "networking", "chamber of commerce",
    "embassy", "consulate", "couchsurfing", "travel meetup", "board games", "dnd",
    "dungeons", "magic the gathering", "mtg", "esports", "board game night", "pub quiz",
    "international community", "english corner", "speech", "tedx", "book club",
    "外国人", "国际", "英语", "外籍", "中英", "老外", "语言交换", "交换角", "外国友人",
]

LOCAL_ONLY_KEYWORDS = [
    "相亲", "本地专场", "家长会", "招聘会", "二手", "转让", "求购", "中介", "房东",
    "微商", "代购", "拼车", "顺风车", "本地群", "闲置",
]

SOURCE_BOOST = {
    "meetup": 25,
    "eventbrite": 25,
    "chamber": 20,
    "rss-expat": 15,
}

CATEGORY_KEYWORDS = {
    "music": ["concert", "livehouse", "live house", "jazz", "演唱会", "音乐会", "音乐节", "festival", "dj", "open mic", "band", "gig", "orchestra", "indie"],
    "art": ["exhibition", "gallery", "art show", "展览", "艺术展", "画展", "摄影展", "art", "museum", "博物馆", "workshop", "手工", "workshop"],
    "tech": ["tech", "hackathon", "meetup", "讲座", "科技", "沙龙", "programming", "开发者", "ai", "startup", "创业", "峰会", "conference", "webinar"],
    "food": ["food festival", "美食节", "品鉴", "tasting", "wine", "啤酒节", "brunch", "food tour", "美食"],
    "sport": ["hiking", "徒步", "running", "跑步", "篮球", "足球", "yoga", "瑜伽", "climbing", "攀岩", "marathon", "马拉松", "骑行", "cycling", "sport", "运动", "board game"],
    "family": ["亲子", "family", "kids", "儿童", "绘本", "parent"],
    "nightlife": ["bar", "club", "party", "酒吧", "夜店", "pub", "night", "ktv", "酒馆", "精酿", "craft beer", "trivia", "quiz"],
    "business": ["networking", "商会", "chamber", "business", "商务", "招聘", "career", "讲座", "论坛"],
    "education": ["language exchange", "语言交换", "课程", "course", "class", "lecture", "演讲", "读书会", "book club", "workshop", "培训"],
    "travel": ["旅游", "travel", "周边游", "citywalk", "徒步", "露营", "camping", "day trip"],
}

CJK_RE = re.compile(r"[一-鿿]")
LATIN_RE = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    if not text:
        return "unknown"
    cjk = len(CJK_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    if cjk and latin:
        return "zh+en"
    if latin:
        return "en"
    if cjk:
        return "zh"
    return "unknown"


def infer_category(text: str) -> str:
    t = (text or "").lower()
    best, best_hits = "other", 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in t)
        if hits > best_hits:
            best, best_hits = cat, hits
    return best


def foreign_score(title: str, description: str, source: str, language: str) -> tuple:
    text = f"{title or ''} {description or ''}".lower()
    score = 0
    for kw in FOREIGN_KEYWORDS:
        if kw in text:
            score += 15
            if score >= 100:
                break
    if language in ("en", "zh+en"):
        score += 20
    for kw in LOCAL_ONLY_KEYWORDS:
        if kw in text:
            score -= 25
    score += SOURCE_BOOST.get((source or "").lower(), 0)
    score = max(0, min(100, score))
    return score, score >= 50
