"""Drafter annotation rules from Lemah Abang DXF 2018.

Source audit: ModelSpace contains 509 TEXT entities on Homepass layer,
with names '001' ... and Tahoma text height 2.0 drawing units.
Homepasses are text, NOT yellow symbol discs. Device glyphs stay at their
georeferenced position; only annotations are shifted to avoid collisions.
"""
import re
from collections import defaultdict
from template_symbols import canonical

def prepare_points(points):
    """Return (original_name, lonlat, canonical_kind, drafter_label).

    Respect existing HP numbers, and assign stable numbers to unnumbered HPs.
    Every PDF/DXF export uses this same deterministic ordering.
    """
    used=set()
    for name, _ in points:
        kind=canonical(name)
        if kind is None and re.fullmatch(r"\s*\d+\s*",str(name or "")):
            kind="HP"
        if kind=="HP":
            m=re.search(r"(\d+)\s*$",str(name or ""))
            if m:
                used.add(int(m.group(1)))
    counter=1
    result=[]
    for name, coord in points:
        kind=canonical(name)
        if kind is None and re.fullmatch(r"\s*\d+\s*",str(name or "")):
            kind="HP"
        if kind in (None,"HP"):
            value=re.search(r"(\d+)\s*$",str(name or ""))
            if value:
                number=int(value.group(1))
            else:
                while counter in used:
                    counter+=1
                number=counter
                used.add(number)
                counter+=1
            label=f"{number:03d}"
            kind="HP"
        else:
            label=str(name or kind).strip()
        result.append((name,coord,kind,label))
    return result


class RectangleIndex:
    """Spatial bins so dense homepass drawings do not require O(N²) scans."""
    def __init__(self,cell=3.0):
        self.cell=max(0.2,float(cell))
        self.items=[]
        self.grid=defaultdict(list)
    def keys(self,box):
        x0,y0,x1,y1=box
        n=self.cell
        for col in range(int(x0//n),int(x1//n)+1):
            for row in range(int(y0//n),int(y1//n)+1):
                yield (col,row)
    def overlap(self,box):
        checked=set()
        x0,y0,x1,y1=box
        for key in self.keys(box):
            for i in self.grid.get(key,()):
                if i in checked:continue
                checked.add(i)
                a,b,c,d=self.items[i]
                if x0<c and x1>a and y0<d and y1>b:
                    return True
        return False
    def insert(self,box):
        i=len(self.items)
        self.items.append(box)
        for key in self.keys(box):
            self.grid[key].append(i)


def plan_labels(prepared, project, bounds, width, size=1.35):
    """Return (kind,label,point_xy,label_xy,font_size) in page/metric units.

    Label rectangles must stay in the map viewport, cannot overlap another
    label or a device symbol. All source-coordinate positions remain intact.
    """
    xmin,ymin,xmax,ymax=bounds
    visible=[]
    for name,coord,kind,label in prepared:
        x,y=project(coord)
        if xmin<=x<=xmax and ymin<=y<=ymax:
            visible.append((kind,label,x,y))
    occupied=RectangleIndex(max(2.2,size*3))
    # Source device symbols stay centered; reserve only the physical glyph,
    # never shift them away from their true coordinate.
    for kind,label,x,y in visible:
        if kind!="HP":
            r=size*.94
            occupied.insert((x-r,y-r,x+r,y+r))
    # Priority: larger network infrastructure labels first, then HP numbers.
    ordering=sorted(enumerate(visible),key=lambda item:
                    (item[1][0]=="HP",item[0]))
    placements={}
    for index,(kind,label,x,y) in ordering:
        fs=size if kind=="HP" else size*.95
        width_est=max(fs*.65,fs*(.59*len(label)+.2))
        h=fs*1.15
        dx= max(.85,fs*.76)
        offsets=[
            (dx,fs*.12),(-dx-width_est,fs*.12),
            (dx,fs*1.16),(-dx-width_est,fs*1.16),
            (dx,-fs*1.13),(-dx-width_est,-fs*1.13),
            (0,fs*2.2),(-width_est/2,-fs*2.2),
            (dx*2,fs*.12),(-dx*2-width_est,fs*.12),
        ]
        choice=None
        for offx,offy in offsets:
            bx=x+offx;by=y+offy
            r=(bx-.10,by-.16,bx+width_est+.10,by+h+.10)
            if (r[0]>=xmin+.20 and r[2]<=xmax-.20 and
                r[1]>=ymin+.20 and r[3]<=ymax-.20 and
                not occupied.overlap(r)):
                choice=(bx,by,r)
                break
        if choice is None:
            # Avoid illegible stacks; keep actual device symbol at coordinate.
            # HP retains a number in the source data; at very dense page
            # extents its label is suppressed rather than overprinted.
            continue
        bx,by,rect=choice
        occupied.insert(rect)
        placements[index]=(kind,label,(x,y),(bx,by),fs)
    return [placements[k] for k in sorted(placements)]
