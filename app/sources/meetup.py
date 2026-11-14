import logging

from .base import RawEvent, Source

log = logging.getLogger("source.meetup")

QUERY = """
query ($lat: Float!, $lon: Float!, $radius: Float!) {
  eventsByLatLon(lat: $lat, lon: $lon, radius: $radius, first: 50, status: UPCOMING) {
    edges { node {
      id name description dateTime
      venue { name address lat lon }
      link
    } }
  }
}
"""


class MeetupSource(Source):
    name = "meetup"

    def __init__(self, fetcher, token: str, radius_km: float = 100.0):
        self.fetcher = fetcher
        self.token = token
        self.radius_km = radius_km

    def fetch(self, city_slug, city_zh, lat, lon):
        payload = {"query": QUERY, "variables": {"lat": lat, "lon": lon, "radius": self.radius_km}}
        data = self.fetcher.post_json(
            "https://api.meetup.com/gql-ext",
            payload,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        if not data:
            return []
        edges = (((data.get("data") or {}).get("eventsByLatLon") or {}).get("edges")) or []
        out = []
        for e in edges:
            node = e.get("node") or {}
            venue = node.get("venue") or {}
            if not node.get("name"):
                continue
            out.append(RawEvent(
                title=node["name"],
                description=node.get("description") or "",
                start_raw=node.get("dateTime") or "",
                venue=venue.get("name") or "",
                address=venue.get("address") or "",
                city=city_slug,
                source="meetup",
                source_url=node.get("link") or "https://www.meetup.com",
                language="en",
                lat=venue.get("lat") or lat,
                lon=venue.get("lon") or lon,
            ))
        log.info("meetup %s: %d raw events", city_slug, len(out))
        return out
