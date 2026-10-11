"""Drafting title block modelled on user-supplied 5-page AS BUILT DRAWING reference.

Recreates the table geometry and legend vocabulary. It is not an exact
reproduction of the proprietary logo or original sign-off/approval entries.
"""
from reportlab.lib.colors import Color

BLACK = (0.08, .08, .08)
BLUE = (.0, .37, .78)


def _line(c,x1,y1,x2,y2,width=.55):
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(width)
    c.line(x1,y1,x2,y2)


def _rect(c,x,y,w,h,width=.6):
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(width)
    c.rect(x,y,w,h)


def _text(c,s,x,y,sz=6,bold=False,max_w=None,center=False):
    value=str(s or "").replace("\n"," ")
    name="Helvetica-Bold" if bold else "Helvetica"
    if max_w:
        while sz>4.0 and c.stringWidth(value,name,sz)>max_w:
            sz-=.2
        if c.stringWidth(value,name,sz)>max_w:
            while value and c.stringWidth(value+"...",name,sz)>max_w:
                value=value[:-1]
            value+="..."
    c.setFillColorRGB(*BLACK)
    c.setFont(name,sz)
    if center:
        c.drawCentredString(x,y,value)
    else:
        c.drawString(x,y,value)


def _icon(c,kind,x,y,rgb):
    c.setStrokeColorRGB(*rgb)
    c.setFillColorRGB(*rgb)
    c.setLineWidth(.9)
    if kind == "pole":
        c.circle(x,y,4.2,stroke=1,fill=0)
        c.circle(x,y,2.0,stroke=1,fill=1)
    elif kind == "odp":
        p=c.beginPath()
        p.moveTo(x-4.5,y-3)
        p.lineTo(x+4.5,y-3)
        p.lineTo(x,y+5)
        p.close()
        c.drawPath(p,stroke=1,fill=0)
    elif kind == "coil":
        c.ellipse(x-5.8,y-2.4,x+5.8,y+2.4,stroke=1,fill=0)
    elif kind == "square":
        c.rect(x-4.2,y-4.2,8.4,8.4,stroke=1,fill=0)
    elif kind == "line":
        c.line(x-7,y,x+7,y)
    elif kind == "stripe":
        c.rect(x-6,y-3,12,6,stroke=1,fill=0)
        for d in (-5,0,5):
            c.line(x+d,y-3,x+d+4,y+3)
    else:
        c.circle(x,y,3.4,stroke=1,fill=1)


def _star_mark(c,center_x,center_y):
    """Vector blue abstract star/bolt; a neutral approximation, not company artwork."""
    c.saveState()
    c.setFillColorRGB(.04,.46,.78)
    def poly(coords):
        p=c.beginPath()
        p.moveTo(*coords[0])
        for xy in coords[1:]:
            p.lineTo(*xy)
        p.close()
        c.drawPath(p,stroke=0,fill=1)
    x,y=center_x,center_y
    poly([(x-26,y-4),(x+17,y+25),(x-1,y+6),(x+24,y+4),(x-5,y-23),(x-2,y-3)])
    c.setFillColorRGB(.02,.20,.44)
    poly([(x+9,y+19),(x+30,y+25),(x+12,y+2),(x+26,y-23),(x+2,y-11)])
    c.setFillColorRGB(*BLACK)
    c.setFont("Helvetica-Bold",10)
    c.drawCentredString(x,center_y-34,"S T A R L I T E")
    c.restoreState()


LEFT_LEGEND = [
    ("NEW POLE 6","pole",(.85,.75,.0)),
    ("NEW POLE 7","pole",(.12,.12,.12)),
    ("NEW POLE 8","pole",(.0,.22,.95)),
    ("NEW POLE 9","pole",(1,.42,.03)),
    ("EXISTING POLE","pole",(.31,.31,.31)),
    ("NEW ODP","odp",(.80,.15,.17)),
    ("EXISTING ODP","odp",(.45,.45,.45)),
    ("NEW ODP 8 HP","odp",(.09,.22,.87)),
    ("NEW ODP 16 HP","odp",(1,.35,.0)),
    ("NEW ODP 24 HP","odp",(.66,.0,.64)),
    ("EXISTING ODP","odp",(.2,.2,.2)),
]
RIGHT_LEGEND = [
    ("EXISTING CLOSURE","coil",(.15,.15,.15)),
    ("NEW CLOSURE","coil",(.91,.10,.13)),
    ("NEW COIL","coil",(.93,.10,.15)),
    ("EXISTING COIL","coil",(.14,.14,.14)),
    ("OUTLET DISTRIBUTION","square",(.10,.22,.95)),
    ("OTHER MARKER","square",(1,.46,.12)),
    ("NEW HANDHOLE","square",(.10,.19,.91)),
    ("EXISTING HANDHOLE","square",(.12,.12,.12)),
    ("BOUNDARY AREA","stripe",(.96,.14,.15)),
    ("EXISTING BRIDGE","stripe",(.58,.58,.58)),
    ("EXISTING HANDHOLE","coil",(.94,.10,.13)),
]
CABLE_LINES = [
    ("DISTRIBUTION 12C",(.69,.24,.98)),
    ("JOINTER/24C",(.95,.80,.03)),
    ("LINE 48C",(.10,.77,.30)),
    ("UG OPTICAL",(0,.31,.95)),
    ("ROAD CENTER",(.19,.19,.19)),
    ("RAILWAY",(.08,.08,.08)),
    ("DROP LINE",(.96,.12,.71)),
]
FEEDER_LINES = [
    ("FDR 12/24",(.96,.10,.14)),
    ("FDR 24/27",(1,.56,.06)),
    ("FDR 48/OT",(.12,.22,.95)),
    ("FDR 72/OT",(.92,.11,.73)),
    ("FDR 96/OT",(.95,.13,.18)),
    ("FDR 144/OT",(.0,.82,.24)),
    ("FDR 288/OT",(.42,.42,.42)),
]


def draw_titleblock(c,x,y,w,h,title,sheetname,index,count,osm):
    """Engineering legend table and sign-off grids in the exact *section order* of reference."""
    c.saveState()
    _rect(c,x,y,w,h)
    top=y+h

    # AS BUILT DRAWING heading
    header_h=35
    _line(c,x,top-header_h,x+w,top-header_h,.85)
    _text(c,"AS BUILT DRAWING",x+w/2,top-25,15,False,w-8,True)

    # Two-column legend with reference symbol ordering
    legend_h=16.4
    legend_bottom=top-header_h-11*legend_h
    mid=x+w*.52
    _line(c,mid,legend_bottom,mid,top-header_h)
    for i in range(11):
        line_y=top-header_h-i*legend_h
        _line(c,x,line_y,x+w,line_y,.45)
        for start,content in ((x,LEFT_LEGEND[i]),(mid,RIGHT_LEGEND[i])):
            label,icon,rgb=content
            _icon(c,icon,start+11,line_y-8.4,rgb)
            _text(c,label,start+22,line_y-10,5.4,True,
                  max_w=(mid-start-25) if start==x else (x+w-start-25))
    _line(c,x,legend_bottom,x+w,legend_bottom,.8)

    # Cable type: 2 side-by-side columns, striped technical legend
    title_h=14
    cable_rows=7
    cable_row=10.0
    _line(c,x,legend_bottom-title_h,x+w,legend_bottom-title_h,.75)
    _text(c,"CABLE TYPE",x+w/2,legend_bottom-10,9,False,w-10,True)
    _line(c,mid,legend_bottom-title_h-cable_rows*cable_row,mid,legend_bottom-title_h)
    for i in range(cable_rows):
        yy=legend_bottom-title_h-i*cable_row
        _line(c,x,yy,x+w,yy,.36)
        for start,entry,end in ((x,CABLE_LINES[i],mid),(mid,FEEDER_LINES[i],x+w)):
            label,color=entry
            _text(c,label,start+3,yy-7.1,4.2,True,max_w=(end-start)*.58)
            c.setStrokeColorRGB(*color)
            c.setLineWidth(1.35)
            c.line(end-41,yy-5,end-5,yy-5)
    cable_bottom=legend_bottom-title_h-cable_rows*cable_row
    _line(c,x,cable_bottom,x+w,cable_bottom,.8)

    # Sponsor mark: approximate vector; labels in reference kept.
    logo_h=67
    logo_bottom=cable_bottom-logo_h
    _star_mark(c,x+w/2,logo_bottom+36)
    _line(c,x,logo_bottom,x+w,logo_bottom,.8)

    # Revision table
    revision_h=56
    rev_bottom=logo_bottom-revision_h
    rev_cols=[x,x+w*.23,x+w*.78,x+w]
    for xx in rev_cols[1:-1]:
        _line(c,xx,rev_bottom,xx,logo_bottom)
    for j in range(5):
        yy=logo_bottom-j*11.2
        _line(c,x,yy,x+w,yy,.5)
    for label,a,b in (("DATE",rev_cols[0],rev_cols[1]),
                      ("REVISION",rev_cols[1],rev_cols[2]),
                      ("SIGN",rev_cols[2],rev_cols[3])):
        _text(c,label,(a+b)/2,logo_bottom-8,6,False,b-a-3,True)

    # Project title: dynamic, does not copy old project or invented signatory.
    project_h=61
    project_bottom=rev_bottom-project_h
    _rect(c,x,project_bottom,w,project_h,.7)
    _text(c,"Project Name",x+4,rev_bottom-10,5.2,True)
    _text(c,title,x+w/2,rev_bottom-24,6.2,True,w-8,True)
    _text(c,sheetname,x+w/2,rev_bottom-36,6.3,True,w-8,True)
    _line(c,x,project_bottom+15,x+w,project_bottom+15,.5)
    _text(c,"Drawing Title:  AS PLAN DRAWING / NETWORK ROUTE PLAN",x+4,project_bottom+5,5.6,False,w-7)

    # Authorship/approval blank by default (never forge sign-offs).
    approve_top=project_bottom
    sign_h=37
    _rect(c,x,approve_top-sign_h,w,sign_h,.7)
    _text(c,"DRAWING SIGN & CHECK",x+w/2,approve_top-12,9,False,w-8,True)
    _text(c,"Drawn by: __________________",x+6,approve_top-24,5.4)
    _text(c,"Checked by: __________________",x+6,approve_top-33,5.4)

    owner_h=27
    owner_top=approve_top-sign_h
    _rect(c,x,owner_top-owner_h,w,owner_h,.7)
    _text(c,"PROJECT CONTROL / APPROVAL",x+w/2,owner_top-11,7.2,True,w-8,True)
    _text(c,"Authorized approval: ______________________",x+5,owner_top-21,5.4)

    # Grid for approval roles
    bottom_grid_top=owner_top-owner_h
    grid_h=max(100,bottom_grid_top-y-69)
    grid_bottom=bottom_grid_top-grid_h
    _rect(c,x,grid_bottom,w,grid_h,.7)
    _line(c,mid,grid_bottom,mid,bottom_grid_top,.5)
    _line(c,x,grid_bottom+grid_h/2,x+w,grid_bottom+grid_h/2,.5)
    roles=[("Prepared by","Survey / Design"),("Checked by","QA / Field Engineer"),
           ("Approved by","Project Manager"),("Verified by","Starlite / Owner")]
    for j,role in enumerate(roles):
        col=j%2
        row=j//2
        xx=x+4 if col==0 else mid+4
        yt=bottom_grid_top-row*grid_h/2
        _text(c,role[0],xx,yt-10,5.8,True,max_w=w/2-9)
        _text(c,role[1],xx,yt-22,5.1,False,max_w=w/2-9)
        _text(c,"____________________",xx,yt-42,5.0,False,max_w=w/2-9)

    # Scale, north arrow, sheet number
    last_h=grid_bottom-y
    _rect(c,x,y,w,last_h,.65)
    _line(c,mid,y,mid,grid_bottom,.6)
    _line(c,mid,y+last_h*.53,x+w,y+last_h*.53,.55)
    _text(c,"N",x+(mid-x)/2,grid_bottom-16,8,True,center=True)
    px=x+(mid-x)/2
    py=y+last_h*.46
    _line(c,px,py-17,px,py+17,1)
    _line(c,px-13,py,px+13,py,1)
    _text(c,"S",px-2,py-23,6,True)
    _text(c,"SCALE  N.T.S.",mid+4,grid_bottom-20,6,True,max_w=w/2-8)
    src=((osm or {}).get("footprint_sources") or {})
    source_label="OSM:{} KML:{} GOOGLE:{}".format(src.get("OSM",0),src.get("KML",0),src.get("GOOGLE",0))
    _text(c,source_label,mid+4,grid_bottom-32,4.9,False,max_w=w/2-8)
    _text(c,"SHEET NUMBER",mid+4,y+last_h*.30,5.2,True)
    _text(c,f"{index+1} OF {count}",mid+w/4,y+9,8,True,center=True)
    c.restoreState()
