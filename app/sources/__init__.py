from .base import RawEvent, Source
from .rss_source import RSSSource
from .douban import DoubanSource
from .damai import DamaiSource
from .meetup import MeetupSource
from .xiaohongshu import XiaohongshuSource


def build_sources(settings, fetcher):
    sources = []
    if settings.rss_feeds:
        sources.append(RSSSource(settings.rss_feeds, fetcher))
    sources.append(DoubanSource(fetcher))
    sources.append(DamaiSource(fetcher))
    sources.append(XiaohongshuSource(fetcher))
    if settings.meetup_token:
        sources.append(MeetupSource(fetcher, settings.meetup_token))
    return sources


__all__ = ["RawEvent", "Source", "build_sources"]
