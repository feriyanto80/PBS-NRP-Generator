"""Offline tests: genuine on-disk gzip cache, HTTP Range resume, no 80MB cap."""
import csv
import gzip
import io
import json
import os
import tempfile
import unittest

from google_auto import TILE_PREFIX, acquire_google
from google_stream import download_tile, extract_region, tile_paths

BBOX=(107.0,-6.1,107.03,-6.07)
URL=TILE_PREFIX+"2e7_buildings.csv.gz"
POLYGON="POLYGON ((107.010 -6.085, 107.011 -6.085, 107.011 -6.086, 107.010 -6.085))"


def fake_tile():
    payload=io.BytesIO()
    with gzip.GzipFile(fileobj=payload,mode="wb") as compressed:
        with io.TextIOWrapper(compressed,encoding="utf-8",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=("longitude","latitude","confidence","geometry"))
            writer.writeheader()
            writer.writerow({"longitude":"107.0105","latitude":"-6.0853",
                             "confidence":"0.87","geometry":POLYGON})
            writer.writerow({"longitude":"108","latitude":"-7",
                             "confidence":"0.95","geometry":POLYGON})
            writer.writerow({"longitude":"107.0105","latitude":"-6.0853",
                             "confidence":"0.64","geometry":POLYGON})
    return payload.getvalue()


class Response(io.BytesIO):
    def __init__(self,data,status,headers):
        super().__init__(data)
        self.status=status
        self.headers=headers


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache=self.tmp.name
        self.bytes=fake_tile()

    def test_range_resume_and_complete_tile_reuse(self):
        seen=[]
        cut=max(15,len(self.bytes)//2)
        def opener(request,timeout=90):
            start=request.get_header("Range")
            seen.append(start)
            if len(seen)==1:
                # First connection closes halfway through declared content.
                return Response(self.bytes[:cut],200,
                                {"Content-Length":str(len(self.bytes))})
            if len(seen)==2:
                self.assertEqual(start,f"bytes={cut}-")
                return Response(self.bytes[cut:],206,{
                    "Content-Length":str(len(self.bytes)-cut),
                    "Content-Range":f"bytes {cut}-{len(self.bytes)-1}/{len(self.bytes)}"})
            self.fail("Download was repeated despite full tile cache")
        result,cache_hit=download_tile(URL,"2e7",self.cache,opener=opener,retries=3,
                                       chunk_bytes=16)
        self.assertFalse(cache_hit)
        self.assertEqual(open(result,"rb").read(),self.bytes)
        self.assertFalse(os.path.exists(result+".part"))
        second,hit=download_tile(URL,"2e7",self.cache,opener=opener)
        self.assertTrue(hit)
        self.assertEqual(second,result)
        self.assertEqual(len(seen),2)

    def test_extract_only_region_and_confidence(self):
        archive=os.path.join(self.cache,"test.csv.gz")
        with open(archive,"wb") as f:
            f.write(self.bytes)
        buildings=extract_region(archive,BBOX,confidence=.70)
        self.assertEqual(len(buildings),1)
        self.assertEqual(len(buildings[0]),4)

    def test_manifest_5880mb_not_skipped_and_region_cached(self):
        features={"type":"FeatureCollection","features":[{"type":"Feature",
          "geometry":{"type":"Polygon","coordinates":[[
              [106.95,-6.3],[107.1,-6.3],[107.1,-6.0],[106.95,-6.0],[106.95,-6.3]]]},
          "properties":{"tile_url":URL,"tile_id":"2e7","size_mb":5880}}]}
        count=[]
        def mock_tile_loader(url,bbox):
            count.append(url)
            return [[(107.010,-6.085),(107.011,-6.085),
                     (107.011,-6.086),(107.010,-6.085)]]
        result=acquire_google(BBOX,cache_dir=self.cache,manifest=features,
                              tile_loader=mock_tile_loader)
        self.assertEqual(result["status"],"ready")
        self.assertEqual(len(result["polygons"]),1)
        self.assertEqual(len(count),1)
        second=acquire_google(BBOX,cache_dir=self.cache,manifest=features,
                              tile_loader=mock_tile_loader)
        self.assertTrue(second["cache_hit"])
        self.assertEqual(len(count),1)

    def test_unique_tile_paths_prevent_path_traversal(self):
        full,partial,meta=tile_paths(self.cache,"../test/",URL)
        self.assertTrue(os.path.realpath(full).startswith(os.path.realpath(self.cache)))
        self.assertTrue(full.endswith(".csv.gz"))


if __name__=="__main__":
    unittest.main()
