"""Offline regression tests: Overpass HTTP 500 failover and tile caching."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

import osm_acquisition as osm


class Response:
    def __init__(self):
        self.raw = io.BytesIO(json.dumps({"elements": [
            {"type": "way", "id": 11, "tags": {"highway": "residential"},
             "geometry": [{"lon": 107.1, "lat": -6.1}, {"lon": 107.11, "lat": -6.11}]},
            {"type": "way", "id": 12, "tags": {"building": "yes"},
             "geometry": [{"lon": 107.1, "lat": -6.1}, {"lon": 107.101, "lat": -6.1}]}
        ]}).encode())
    def __enter__(self): return self.raw
    def __exit__(self, *args): pass


class OSMTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bbox = (107.1, -6.1, 107.104, -6.096)

    def test_http_500_switches_server_and_uses_cache(self):
        calls = []
        def opener(request, timeout=45):
            calls.append(request.full_url)
            if "broken" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 500, "Internal Server Error", {}, None)
            return Response()
        kwargs = {"cache_dir": self.tmp.name, "opener": opener, "sleep": lambda sec: None,
                  "endpoints": ("https://broken.example/api/interpreter",
                                "https://working.example/api/interpreter")}
        data = osm.fetch_osm(self.bbox, **kwargs)
        self.assertEqual(len(data["roads"]), 1)
        self.assertEqual(len(data["buildings"]), 1)
        self.assertFalse(data["partial"])
        self.assertEqual(len(calls), 2)
        osm.fetch_osm(self.bbox, **kwargs)
        self.assertEqual(len(calls), 2)

    def test_http_403_on_one_mirror_tries_next(self):
        attempts = []
        def opener(request, timeout=45):
            attempts.append(request.full_url)
            if "forbidden" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)
            return Response()
        data = osm.fetch_osm(self.bbox, cache_dir=self.tmp.name, opener=opener,
                             sleep=lambda sec: None,
                             endpoints=("https://forbidden.example/api/interpreter",
                                        "https://working.example/api/interpreter"))
        self.assertEqual(len(data["roads"]), 1)
        self.assertEqual(len(attempts), 2)

    def test_large_area_is_tiled(self):
        calls = []
        def opener(request, timeout=45):
            calls.append(request)
            return Response()
        osm.fetch_osm((107.1, -6.1, 107.14, -6.06), cache_dir=self.tmp.name,
                      opener=opener, endpoints=("https://working.example/api/interpreter",))
        self.assertEqual(len(calls), 9)

    def test_all_500_fails_explicitly(self):
        def opener(request, timeout=45):
            raise urllib.error.HTTPError(request.full_url, 500, "Error", {}, None)
        with self.assertRaisesRegex(RuntimeError, "OSM gagal"):
            osm.fetch_osm(self.bbox, cache_dir=self.tmp.name, opener=opener,
                          sleep=lambda sec: None,
                          endpoints=("https://broken.example/api/interpreter",))

    def test_corrupt_cache_is_recovered(self):
        path = osm._cache_name(self.tmp.name, self.bbox)
        Path(path).write_text("{invalid", encoding="utf8")
        osm.fetch_osm(self.bbox, cache_dir=self.tmp.name,
                      opener=lambda request, timeout=45: Response(),
                      endpoints=("https://working.example/api/interpreter",))
        self.assertIsNotNone(osm._read_cache(path))

    def test_oversize_area_rejected(self):
        with self.assertRaisesRegex(ValueError, "terlalu luas"):
            osm.fetch_osm((107.0, -7.0, 108.0, -6.0),
                          cache_dir=self.tmp.name,
                          endpoints=("https://working.example/api/interpreter",))


if __name__ == "__main__":
    unittest.main()
