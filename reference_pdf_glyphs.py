"""Use the actual printed Lemah Abang PDF legend glyphs on the map.

Extracts ONLY individual device glyphs from the sanitized static-reference
PDF included in the separately distributed template/ folder; no confidential
map, identity, approvals or historic customer information is copied.
Fallback to editable vector symbols whenever the reference is unavailable.
"""
from functools import lru_cache
from io import BytesIO
from template_symbols import LEGEND_IDS_LEFT, LEGEND_IDS_RIGHT

_FIRST_ROW_Y = 67.25
_ROW_SPACING = 21.555
_COLUMNS = ((1003.7, 7.0), (1083.7, 10.0))

def _position(kind):
    for col, identifiers in enumerate((LEGEND_IDS_LEFT, LEGEND_IDS_RIGHT)):
        if kind in identifiers:
            return col, identifiers.index(kind)
    return None

@lru_cache(maxsize=32)
def _load_reference_icon(kind, path, mtime):
    import fitz
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    position = _position(kind)
    if position is None:
        return None
    col, row = position
    x, hw = _COLUMNS[col]
    y = _FIRST_ROW_Y + row * _ROW_SPACING
    crop = fitz.Rect(x-hw, y-7.0, x+hw, y+7.0)
    doc = fitz.open(path)
    try:
        page = doc[0]
        if page.rotation:
            page.remove_rotation()
            page = doc[0]
        if abs(page.rect.width-1191) > 8 or abs(page.rect.height-842) > 8:
            return None
        pixels = page.get_pixmap(matrix=fitz.Matrix(6,6),
                                 clip=crop, colorspace=fitz.csRGB, alpha=False)
        img = Image.frombytes("RGB", (pixels.width,pixels.height),
                              pixels.samples).convert("RGBA")
        bitmap=img.load()
        colored=0
        for yy in range(img.height):
            for xx in range(img.width):
                r,g,b,_=bitmap[xx,yy]
                alpha=max(0,min(255,round((255-min(r,g,b))*8)))
                colored += alpha>60
                bitmap[xx,yy]=(r,g,b,alpha)
        if colored<8:
            return None
        buffer=BytesIO()
        img.save(buffer,format="PNG")
        buffer.seek(0)
        return (ImageReader(buffer), crop.width*25.4/72, crop.height*25.4/72)
    finally:
        doc.close()

def draw_reference_pdf_glyph(canvas, kind, x, y):
    """Stamp true AutoCAD PDF glyph at a map point in A3-mm coordinates."""
    if _position(kind) is None:
        return False
    try:
        import os
        from exact_template import find_reference
        path=find_reference("pdf")
        if not path:
            return False
        resource=_load_reference_icon(kind,path,os.path.getmtime(path))
        if resource is None:
            return False
        img,w,h=resource
        canvas.drawImage(img,x-w/2,y-h/2,w,h,mask="auto",
                         preserveAspectRatio=False)
        return True
    except Exception:
        return False
