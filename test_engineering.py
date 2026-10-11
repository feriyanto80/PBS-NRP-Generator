import tempfile
import unittest
from pathlib import Path
from reportlab.lib.pagesizes import A3, landscape
import ezdxf
from engineering_render import _polyline_offsets, draw_pdf, draw_dxf

class EngineeringTest(unittest.TestCase):
    def test_offset_edges(self):
        a,b=_polyline_offsets([(0,0),(10,0)],3)
        self.assertEqual(a,[(0,3),(10,3)])
        self.assertEqual(b,[(0,-3),(10,-3)])

    def test_pdf_and_dxf(self):
        lines=[('FEEDER 96C','FEEDER',[(107,-6),(107.004,-6.001)])]
        points=[('ODP 01',(107.004,-6.001))]
        bb=(106.999,-6.004,107.009,-5.999)
        sheets=[('Overview',bb),('NW',bb),('NE',bb),('SW',bb),('SE',bb)]
        osm={'roads':[[(107,-6),(107.007,-6.002)]],
             'buildings':[[(107.002,-6.0005),(107.0025,-6.0005),(107.0025,-6.001),(107.002,-6.0005)]],
             'road_widths':[6.0], 'partial':False}
        with tempfile.TemporaryDirectory() as directory:
            pdf=Path(directory)/'engineering.pdf'
            dxf=Path(directory)/'engineering.dxf'
            draw_pdf(str(pdf),lines,points,None,*landscape(A3),'Test',sheets,osm)
            self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))
            self.assertGreater(pdf.stat().st_size,4000)
            draw_dxf(str(dxf),lines,points,sheets,osm)
            m=ezdxf.readfile(str(dxf)).modelspace()
            self.assertEqual(len(m.query('LWPOLYLINE[layer=="OSM_ROAD_EDGES"]')),2)
            self.assertEqual(len(m.query('LWPOLYLINE[layer=="OSM_BUILDING_FOOTPRINT"]')),1)

if __name__=='__main__':
    unittest.main()
