from dataclasses import dataclass, field


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


class Source:
    name = "base"

    def fetch(self, city_slug: str, city_zh: str, lat: float, lon: float):
        raise NotImplementedError
