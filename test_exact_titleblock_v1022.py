"""Full source titleblock can be copied only for explicitly validated project.

The page-specific raster copy must not include anything from the source map.
Tests use synthetic 5-page A3 vector drawings, no client/project data.
"""
import tempfile
import unittest
from pathlib import Path
import fitz
from exact_template import overlay_pdf_upper_titleblock

class FullLemahabangTitleblockTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.reference=self.root/"reference.pdf"
        doc=fitz.open()
        for i in range(5):
            page=doc.new_page(width=1191,height=842)
            # Distinct color per page proves source pages are not recycled.
            color=(0.9,0.05,0.05) if i%2==0 else (0.05,0.1,0.9)
            page.draw_rect(fitz.Rect(1000,570,1050,630),
                           color=color,fill=color)
            # Map content beyond template must never be transferred.
            page.draw_rect(fitz.Rect(100,100,150,150),
                           color=(1,0,0),fill=(1,0,0))
        doc.save(self.reference); doc.close()

    def _make_output(self,count):
        path=self.root/("out"+str(count)+".pdf")
        doc=fitz.open()
        for i in range(count):
            page=doc.new_page(width=1191,height=842)
            page.draw_rect(fitz.Rect(1000,570,1050,630),
                           color=(0,1,0),fill=(0,1,0))
        doc.save(path); doc.close()
        return path

    def _pixel(self,page,x,y):
        pix=page.get_pixmap(clip=fitz.Rect(x,y,x+1,y+1),
                            colorspace=fitz.csRGB)
        return tuple(pix.samples[:3])

    def test_identical_five_sheet_copy_includes_footer_per_page(self):
        output=self._make_output(5)
        self.assertEqual(overlay_pdf_upper_titleblock(
            output,self.reference,full_source_project=True),5)
        with fitz.open(output) as doc:
            self.assertEqual(len(doc),5)
            red=self._pixel(doc[0],1020,590)
            blue=self._pixel(doc[1],1020,590)
            self.assertGreater(red[0],red[2]*2)
            self.assertGreater(blue[2],blue[0]*2)
            # Original network map at x=100 must not be copied.
            self.assertTrue(all(c>=248 for c in self._pixel(doc[0],110,110)))

    def test_no_project_footer_without_matching_five_page_plan(self):
        output=self._make_output(4)
        self.assertEqual(overlay_pdf_upper_titleblock(
            output,self.reference,full_source_project=True),4)
        with fitz.open(output) as doc:
            # Lower green output content remains untouched in nonmatch case.
            color=self._pixel(doc[0],1020,590)
            self.assertGreater(color[1],color[0]*2)

if __name__=="__main__":
    unittest.main()
