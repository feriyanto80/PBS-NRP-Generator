"""PBS NRP v1.0.22.6: road-only cache repair and strict CAD symbol authority."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from osm_acquisition import _cache_name,_write_cache
from osm_road_recovery import (
    fetch_roads_only, merge_recovered_roads, _road_cache_name,
)
from drafter_annotations import prepare_points,plan_symbols,plan_labels
from template_symbols import canonical,LEGEND_IDS_LEFT,LEGEND_IDS_RIGHT


BBOX=(107.10,-6.10,107.104,-6.096)
ROAD={"type":"way","id":1122,"tags":{"highway":"residential"},
      "geometry":[{"lon":107.1,"lat":-6.10},
                  {"lon":107.102,"lat":-6.098}]}
HOUSE={"type":"way","id":991,"tags":{"building":"yes"},
       "geometry":[{"lon":107.1,"lat":-6.1},
                   {"lon":107.1002,"lat":-6.0999}]}


class Response:
    def __init__(self,payload):
        self.stream=io.BytesIO(json.dumps(payload).encode())
    def __enter__(self): return self.stream
    def __exit__(self,*args): pass


class RoadRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=self.temp.name
        self.kwargs={"cache_dir":self.folder,
                     "endpoints":("https://one.example/api/interpreter",),
                     "sleep":lambda delay:None,"clock":lambda:1000}

    def test_zero_roads_in_old_shared_cache_forces_highway_only(self):
        # The original v1.0.22.5 shared cache considers this a success.
        _write_cache(_cache_name(self.folder,BBOX),{
            "features":[{"key":"buildings:991","category":"buildings",
                         "points":[(107.1,-6.1),(107.1002,-6.0999)]}]})
        calls=[]
        def fetch(request,timeout=36):
            query=str(request.data)
            calls.append(query)
            self.assertIn("highway",query)
            self.assertNotIn("building",query)
            return Response({"elements":[ROAD,HOUSE]})
        r=fetch_roads_only(BBOX,opener=fetch,**self.kwargs)
        self.assertEqual(r["status"],"READY")
        self.assertEqual(len(r["roads"]),1)
        self.assertEqual(len(calls),1)
        self.assertTrue(Path(_road_cache_name(self.folder,BBOX)).exists())
        cached=fetch_roads_only(BBOX,opener=lambda *a,**k:
                                self.fail("road cache not reused"),**self.kwargs)
        self.assertEqual(cached["cached_tiles"],1)

    def test_http_429_failover_does_not_retry_unboundedly(self):
        calls=[]
        def fetch(request,timeout=36):
            calls.append(request.full_url)
            if "broken.example" in request.full_url:
                raise urllib.error.HTTPError(request.full_url,429,
                                             "Too Many Requests",{},None)
            return Response({"elements":[ROAD]})
        r=fetch_roads_only(BBOX,opener=fetch,cache_dir=self.folder,
                          endpoints=("https://broken.example/api/interpreter",
                                     "https://healthy.example/api/interpreter"),
                          sleep=lambda t:None,clock=lambda:1000)
        self.assertEqual(r["status"],"READY")
        self.assertEqual(len(r["roads"]),1)
        self.assertEqual(len(calls),2)

    def test_empty_is_a_distinct_healthy_status_and_refreshable(self):
        calls=[]
        def fetch(request,timeout=36):
            calls.append(request.full_url)
            return Response({"elements":[]})
        result=fetch_roads_only(BBOX,opener=fetch,**self.kwargs)
        self.assertEqual(result["status"],"COMPLETE_EMPTY")
        self.assertEqual(len(calls),1)
        fetch_roads_only(BBOX,opener=fetch,**self.kwargs)
        self.assertEqual(len(calls),1)
        # User pressed Retry Jalan Saja. Re-query verified empty cache.
        fetch_roads_only(BBOX,opener=fetch,force_empty=True,**self.kwargs)
        self.assertEqual(len(calls),2)

    def test_failure_not_mistaken_as_empty_or_success(self):
        def fetch(request,timeout=36):
            raise urllib.error.HTTPError(request.full_url,503,
                                         "Service Unavailable",{},None)
        result=fetch_roads_only(BBOX,opener=fetch,**self.kwargs)
        self.assertEqual(result["status"],"FAILED")
        self.assertEqual(result["failed_tiles"],1)
        self.assertEqual(result["successful_tiles"],0)
        self.assertFalse(Path(_road_cache_name(self.folder,BBOX)).exists())

    def test_road_merge_keeps_previous_osm_google_buildings(self):
        polygons=[[ (107.100,-6.100),(107.101,-6.100),(107.101,-6.099),
                    (107.100,-6.100)]]
        before={"buildings":polygons,
                "roads":[[(107.1,-6.1),(107.101,-6.1)]],
                "_road_surfaces_v108":[{"stale":True}]}
        after=merge_recovered_roads(before,{
            "roads":[[(107.102,-6.1),(107.103,-6.1)]],
            "status":"PARTIAL","successful_tiles":8,
            "failed_tiles":1,"empty_tiles":0,"warnings":[]})
        self.assertEqual(after["buildings"],polygons)
        self.assertEqual(len(after["roads"]),2)
        self.assertTrue(after["partial"])
        self.assertNotIn("_road_surfaces_v108",after)
        self.assertEqual(len(before["roads"]),1)


class StrictSymbolTests(unittest.TestCase):
    def test_unclassified_is_never_a_circle_or_label(self):
        points=[("Unclassified Pole 42",(107.1,-6.1)),
                ("HP 029",(107.101,-6.1)),
                ("T6",(107.102,-6.1)),
                ("ODP 03",(107.103,-6.1))]
        prepared=prepare_points(points)
        self.assertEqual([q[2] for q in prepared],
                         ["UNKNOWN","HP","T6","ODP"])
        project=lambda xy:(xy[0]*1000,xy[1]*1000)
        bb=(107000,-7000,108000,-5000)
        kinds=[q[0] for q in plan_symbols(prepared,project,bb)]
        self.assertIn("T6",kinds)
        self.assertIn("ODP",kinds)
        self.assertNotIn("UNKNOWN",kinds)
        self.assertNotIn("HP",kinds)
        labels=[q[1] for q in plan_labels(prepared,project,bb)]
        self.assertNotIn("Unclassified Pole 42",labels)
        self.assertIn("029",labels)

    def test_legends_have_no_generic_waypoint_marker(self):
        ids=set(LEGEND_IDS_LEFT+LEGEND_IDS_RIGHT)
        self.assertNotIn("UNKNOWN",ids)
        self.assertNotIn("HP",ids)

if __name__=="__main__":
    unittest.main()
