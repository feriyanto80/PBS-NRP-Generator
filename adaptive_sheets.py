"""Adaptive NRP Sheet Planning — network-aware pagination.

Overview + dynamic detail sheets, selected by actual network point/line density.
Grid partitions are recursively split around weighted feature median instead of
hard-coding four quadrants. Adjacent sheets overlap to preserve continuity.
This creates drafting VIEWPORTS only, not additional network geometry.
"""
import math
from collections import Counter


def _metric(lon, lat, midlat):
    return float(lon) * math.cos(math.radians(midlat)) * 111320.0, float(lat) * 110574.0


def _rect_counts(region, samples):
    x0,y0,x1,y1=region
    pts=links=0
    for x,y,kind in samples:
        if x0<=x<=x1 and y0<=y<=y1:
            if kind==1:
                pts+=1
            else:
                links+=1
    return pts,links


def _split_region(region, samples, min_dimension_m):
    x0,y0,x1,y1=region
    width=x1-x0
    height=y1-y0
    if max(width,height)<2*min_dimension_m:
        return None
    # Split along the longer map axis, unless the feature spread is narrower.
    axis=0 if width>=height else 1
    candidates=[v[axis] for v in samples if region[0]<=v[0]<=region[2]
                and region[1]<=v[1]<=region[3]]
    if len(candidates)<8:
        return None
    candidates.sort()
    center=candidates[len(candidates)//2]
    low=(x0 if axis==0 else y0)
    high=(x1 if axis==0 else y1)
    # Prevent tiny slivers around heavily clustered point coordinates.
    cut=max(low+.26*(high-low),min(high-.26*(high-low),center))
    if cut-low<min_dimension_m or high-cut<min_dimension_m:
        return None
    if axis==0:
        left=(x0,y0,cut,y1)
        right=(cut,y0,x1,y1)
    else:
        left=(x0,y0,x1,cut)
        right=(x0,cut,x1,y1)
    pl,ll=_rect_counts(left,samples)
    pr,lr=_rect_counts(right,samples)
    if (pl+ll)<2 or (pr+lr)<2:
        return None
    return left,right


def _projected_bounds(bbox):
    west,south,east,north=map(float,bbox)
    if not (-180<=west<east<=180 and -90<=south<north<=90):
        raise ValueError("Boundary jaringan tidak valid")
    midlat=(south+north)/2
    a=_metric(west,south,midlat)
    b=_metric(east,north,midlat)
    return (a[0],a[1],b[0],b[1]),midlat


def plan_sheets(lines, points, bbox, max_details=24,
                target_points=230, target_lines=300,
                overlap=.075, min_dimension_m=26):
    """Return (sheets, metadata).

    The overview always covers the complete network bbox; detail sheet count
    is density-dependent. Limit sheets to avoid a runaway multi-hundred-page
    export. Each detail rectangle gains a modest spatial overlap, while
    adjacency is visible in the sheet numbering.
    """
    if max_details<1:
        raise ValueError("max_details harus >= 1")
    whole,midlat=_projected_bounds(bbox)
    samples=[]
    for item in points:
        try:
            x,y=_metric(item[1][0],item[1][1],midlat)
            if math.isfinite(x) and math.isfinite(y):
                samples.append((x,y,1))
        except (TypeError,ValueError,IndexError):
            continue
    # Use a representative point for each line and densify long routes.
    # This helps preserve cable corridors instead of counting points alone.
    for name,category,line in lines:
        if not line:
            continue
        positions=[]
        for p in line:
            try:
                positions.append(_metric(p[0],p[1],midlat))
            except (TypeError,ValueError,IndexError):
                continue
        if len(positions)<2:
            continue
        # One representative per line, plus split probes on long segments.
        mx=(min(x for x,y in positions)+max(x for x,y in positions))/2
        my=(min(y for x,y in positions)+max(y for x,y in positions))/2
        samples.append((mx,my,0))
        if category in ("FEEDER","SUBFEEDER") and len(positions)>2:
            # A long trunk should influence sheets along its span.
            stride=max(1,len(positions)//4)
            for q in positions[::stride][1:4]:
                samples.append((q[0],q[1],0))
    available=sum(kind for _,_,kind in samples)
    lines_count=len(samples)-available
    if not samples:
        return [("Overview",tuple(bbox))],{
            "details":0,"points":0,"routes":0,"method":"ADAPTIVE_NETWORK_DENSITY",
            "overlap_fraction":overlap,"warnings":["Jaringan kosong"]}
    partitions=[whole]
    while len(partitions)<max_details:
        workload=[]
        for index,part in enumerate(partitions):
            p,l=_rect_counts(part,samples)
            score=max(p/max(target_points,1),l/max(target_lines,1))
            workload.append((score,index,p,l))
        workload.sort(reverse=True)
        score,index,p,l=workload[0]
        if score<=1.0:
            break
        result=_split_region(partitions[index],samples,min_dimension_m)
        if result is None:
            # Other partitions might still be splitable.
            found=False
            for _,candidate,_,_ in workload[1:]:
                result=_split_region(partitions[candidate],samples,min_dimension_m)
                if result:
                    index=candidate
                    found=True
                    break
            if not found:
                break
        partitions[index:index+1]=list(result)
    # Detail sheets only when overview density calls for magnification.
    need_detail=available>target_points or lines_count>target_lines
    if not need_detail:
        partitions=[]
    # Reading order: north-to-south then west-to-east.
    partitions.sort(key=lambda b:(-(b[1]+b[3])/2,(b[0]+b[2])/2))
    to_geo=lambda x,y:(x/(111320.0*math.cos(math.radians(midlat))),y/110574.0)
    sheets=[("Overview",tuple(bbox))]
    workload=[]
    for i,(x0,y0,x1,y1) in enumerate(partitions,1):
        dx,dy=x1-x0,y1-y0
        # Expand 7.5% or up to 15m to keep features readable at sheet joins.
        ox=max(5.0,min(15.0,dx*overlap))
        oy=max(5.0,min(15.0,dy*overlap))
        rect=(max(whole[0],x0-ox),max(whole[1],y0-oy),
              min(whole[2],x1+ox),min(whole[3],y1+oy))
        a=to_geo(rect[0],rect[1])
        b=to_geo(rect[2],rect[3])
        npoints,nroutes=_rect_counts((x0,y0,x1,y1),samples)
        name=f"Detail {i:02d} - {npoints} titik, {nroutes} ruas"
        sheets.append((name,(a[0],a[1],b[0],b[1])))
        workload.append({"index":i,"points":npoints,"routes":nroutes,
                         "name":name})
    report={
      "method":"ADAPTIVE_NETWORK_DENSITY",
      "overview":1,"details":len(partitions),"total":len(sheets),
      "network_points":available,"network_route_samples":lines_count,
      "max_details":max_details,
      "target_points_per_sheet":target_points,
      "target_routes_per_sheet":target_lines,
      "overlap_fraction":overlap,
      "sheet_workload":workload,
      "warnings":(["Batas jumlah sheet tercapai; cek keterbacaan label"]
                  if len(partitions)>=max_details else []),
    }
    return sheets,report
