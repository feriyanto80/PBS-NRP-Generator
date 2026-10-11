"""v1.0.20 regression: original 2018 CAD devices, HP text-only, window behavior."""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ezdxf

from drafter_annotations import prepare_points,plan_labels
from template_symbols import canonical
from original_dxf_blocks import import_original_blocks,insert_original


class OriginalDrafterPoints(unittest.TestCase):
    def test_homepass_uses_three_digit_text(self):
        points=[("HP 001",(107,-6.2)),("002",(107.00001,-6.2)),
                ("HP",(107.00002,-6.2)),("ODP 8 HP 008",(107.00003,-6.2))]
        items=prepare_points(points)
        self.assertEqual([(e[2],e[3]) for e in items],
                         [("HP","001"),("HP","002"),("HP","003"),
                          ("ODP","ODP 8 HP 008")])

    def test_collision_grid(self):
        points=[("HP 001",(0,0)),("HP 002",(.000001,0)),
                ("HP 003",(.000002,0)),("ODP 01",(.000003,0))]
        prepared=prepare_points(points)
        project=lambda xy:(100+xy[0]*10000,100+xy[1]*10000)
        labels=plan_labels(prepared,project,(80,80,140,140),1.4)
        self.assertEqual(len(labels),len(points))
        self.assertEqual({label for _kind,label,*_ in labels},
                         {"001","002","003","ODP 01"})
        self.assertEqual(labels,plan_labels(prepared,project,(80,80,140,140),1.4))

    def test_legacy_numbered_hp(self):
        self.assertEqual(prepare_points([("123",(0,0))])[0][3],"123")
        self.assertEqual(prepare_points([("HP 004",(0,0))])[0][3],"004")


class ExactCADNoReconstruction(unittest.TestCase):
    def test_source_native_hatch_and_mtext_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"sample.dxf"
            source=ezdxf.new("R2018")
            block=source.blocks.new("T6")
            block.add_circle((388,296),1.5)
            block.add_mtext("T6",dxfattribs={"insert":(388,296)})
            source.saveas(path)
            target=ezdxf.new("R2018")
            with patch("exact_template.find_reference",return_value=str(path)):
                self.assertTrue(import_original_blocks(target))
            self.assertTrue(insert_original(target,target.modelspace(),"T6",(100,200)))
            self.assertEqual(len(target.modelspace().query("INSERT")),1)
            self.assertEqual(len(target.blocks.get("T6").query("MTEXT")),1)
            block_ref=next(iter(target.modelspace().query("INSERT")))
            from ezdxf import bbox
            limits=bbox.extents(list(source.blocks.get("T6")),fast=True)
            centre=(limits.extmin.x+limits.extmax.x)/2
            self.assertAlmostEqual(block_ref.dxf.insert.x+centre*block_ref.dxf.xscale,100,places=3)

    def test_source_homepass_has_no_symbol(self):
        from reference_pdf_layout import _pdf_point
        class MockCanvas:
            def __init__(self):self.calls=[]
            def saveState(self):pass
            def restoreState(self):pass
            def setFillColorRGB(self,*args):pass
            def setFont(self,*args):pass
            def drawString(self,*args):self.calls.append(args)
        c=MockCanvas()
        with patch("reference_pdf_layout._system_font",return_value="Helvetica"):
            _pdf_point(c,(10,11),"HP 001",{},1)
        self.assertEqual(c.calls[0][2],"001")

if __name__=="__main__":
    unittest.main()
