"""Adaptive NRP sheet pagination and busy-state regression."""
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch
from adaptive_sheets import plan_sheets
from responsive_ui import ResponsiveNRP


def make_network(nx,ny,bbox=(107.0,-6.1,107.03,-6.07)):
    x0,y0,x1,y1=bbox
    points=[]
    lines=[]
    for i in range(nx):
        for j in range(ny):
            x=x0+(i+.5)*(x1-x0)/nx
            y=y0+(j+.5)*(y1-y0)/ny
            points.append((f"HP-{i}-{j}",(x,y)))
            lines.append((f"Distribution-{i}-{j}","DISTRIBUSI",
                         [(x,y),(x+0.00008,y+0.00006)]))
    return lines,points,bbox


class AdaptiveSheetTests(unittest.TestCase):
    def test_small_project_requires_only_overview(self):
        lines,points,bbox=make_network(6,6)
        pages,report=plan_sheets(lines,points,bbox)
        self.assertEqual(len(pages),1)
        self.assertEqual(report["details"],0)

    def test_dense_project_more_than_fixed_five(self):
        lines,points,bbox=make_network(50,30)
        pages,report=plan_sheets(lines,points,bbox)
        self.assertGreater(len(pages),5)
        self.assertEqual(report["total"],len(pages))
        self.assertLessEqual(len(pages),25)
        self.assertEqual(pages[0][0],"Overview")
        self.assertEqual(pages[0][1],bbox)

    def test_line_only_density_triggers_details(self):
        lines,points,bbox=make_network(22,18)
        pages,report=plan_sheets(lines,[],bbox)
        self.assertGreater(len(pages),1)

    def test_all_detail_boxes_within_overview(self):
        lines,points,bbox=make_network(50,20)
        pages,report=plan_sheets(lines,points,bbox)
        for title,(w,s,e,n) in pages[1:]:
            self.assertGreater(e,w)
            self.assertGreater(n,s)
            self.assertGreaterEqual(w,bbox[0]-1e-9)
            self.assertGreaterEqual(s,bbox[1]-1e-9)
            self.assertLessEqual(e,bbox[2]+1e-9)
            self.assertLessEqual(n,bbox[3]+1e-9)

    def test_does_not_exceed_configured_limit(self):
        lines,points,bbox=make_network(50,30)
        pages,_=plan_sheets(lines,points,bbox,max_details=7)
        self.assertLessEqual(len(pages),8)


class ExportStateTests(unittest.TestCase):
    def test_generate_locked_for_active_acquisition_and_restored(self):
        root=tk.Tk()
        try:
            app=ResponsiveNRP(root)
            app._running=True
            app._osm_loading=True
            app._update_generate_button()
            self.assertEqual(app.generate_button.cget("state"),"disabled")
            app._running=False
            app._osm_loading=False
            app._update_generate_button()
            self.assertEqual(app.generate_button.cget("state"),"normal")
        finally:
            root.destroy()

    def test_project_has_dynamic_sheet_choices(self):
        root=tk.Tk()
        try:
            app=ResponsiveNRP(root)
            lines,points,_=make_network(40,30)
            app.lines=lines
            app.points=points
            app._rebuild_sheet_plan()
            self.assertGreater(len(app._planned_sheets),5)
            self.assertEqual(len(app.sheet.cget("values")),len(app._planned_sheets))
        finally:
            root.destroy()


if __name__=="__main__":
    unittest.main()
