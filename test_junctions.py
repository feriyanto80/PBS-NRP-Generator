"""Road corridor topology regression tests for T, cross and right-angle junctions."""
import unittest
from road_topology import build_road_surfaces, iter_road_boundaries

LON, LAT = 107.0, -6.0
def xy(x,y):
    return LON+x/110700.0, LAT+y/110574.0

def osm(*lines):
    return {"roads":[[xy(*p) for p in line] for line in lines],
            "road_widths":[6.0]*len(lines)}

class JunctionTopologyTests(unittest.TestCase):
    def assert_one_boundary(self, data):
        polygons=build_road_surfaces(data)
        self.assertEqual(len(polygons),1)
        self.assertEqual(len(list(iter_road_boundaries(data))),1)
        self.assertFalse(polygons[0]["holes"])
        self.assertEqual(polygons[0]["exterior"][0],
                         polygons[0]["exterior"][-1])
        self.assertIs(polygons,build_road_surfaces(data))

    def test_t_junction_no_internal_overlapping_edges(self):
        self.assert_one_boundary(osm([(-30,0),(0,0),(30,0)],
                                     [(0,-25),(0,0)]))

    def test_cross_intersection_one_contour(self):
        self.assert_one_boundary(osm([(-40,0),(40,0)],
                                     [(0,-40),(0,40)]))

    def test_bent_road_no_double_miter_edges(self):
        self.assert_one_boundary(osm([(-30,-10),(0,-10),(0,20)]))

    def test_duplicate_reversed_centerline_is_dissolved(self):
        self.assert_one_boundary(osm([(-25,0),(25,0)],
                                     [(25,0),(-25,0)]))

    def test_disconnected_roads_are_not_falsely_joined(self):
        parts=build_road_surfaces(osm([(-50,0),(-35,0)],
                                      [(35,0),(50,0)]))
        self.assertEqual(len(parts),2)

if __name__=="__main__":
    unittest.main()
