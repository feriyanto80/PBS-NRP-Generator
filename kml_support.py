"""KML and KMZ input support for PBS Network Route Plan Generator."""
import math
import os
import zipfile
from xml.etree import ElementTree as ET


def _tag_name(tag):
    return tag.rsplit('}', 1)[-1]


def parse_kml_bytes(source):
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise ValueError(f'XML KML tidak valid: {exc}') from exc
    lines, points = [], []
    # KML geometry names are often numeric (e.g. 001, 002); the type lives in
    # the parent Folder or ExtendedData. Keep that authority so symbol classes
    # in the PDF/legend and CAD blocks match the actual device type.
    parents={child:parent for parent in root.iter() for child in parent}
    def get_type(placemark):
        tokens=[]
        for entry in placemark.iter():
            if _tag_name(entry.tag)=="Data":
                key=(entry.get("name") or "").lower()
                if any(k in key for k in ("type","device","perangkat","symbol","jenis")):
                    value=next((c.text for c in entry if _tag_name(c.tag)=="value"),None)
                    if value:tokens.append(str(value))
            if _tag_name(entry.tag)=="SimpleData":
                key=(entry.get("name") or "").lower()
                if any(k in key for k in ("type","device","perangkat","symbol","jenis")):
                    if entry.text:tokens.append(entry.text)
        current=parents.get(placemark)
        for _ in range(8):
            if current is None:break
            if _tag_name(current.tag) in ("Folder","Document"):
                folder=next((c.text for c in current if _tag_name(c.tag)=="name"),None)
                if folder:tokens.append(folder)
            current=parents.get(current)
        # Only class names appearing as whole words count as authority.
        from template_symbols import canonical
        for text in tokens:
            value=canonical(text)
            if value:
                return value
        return None
    for placemark in root.iter():
        if _tag_name(placemark.tag) != 'Placemark':
            continue
        name = next(((n.text or '').strip() for n in placemark if _tag_name(n.tag) == 'name'), '')
        role=get_type(placemark)
        # If the own name is a numeric ID but the Folder says T7 or ODP,
        # provide the type to the downstream symbol classifier.
        from template_symbols import canonical
        styled_name=name
        own_kind=canonical(name)
        # A generic HP/numeric label does not override explicit device
        # authority from Folder or ExtendedData (e.g. ODP/001/HP 008).
        if role and (not own_kind or (own_kind=="HP" and role!="HP")):
            styled_name=(role+" "+name).strip()
        upper = (name+" "+(role or "")).upper()
        category = ('FEEDER' if 'FEEDER' in upper and 'SUB' not in upper else
                    'SUBFEEDER' if 'SUB' in upper else 'DISTRIBUSI')
        for geometry in placemark.iter():
            kind = _tag_name(geometry.tag)
            if kind not in ('LineString', 'Point'):
                continue
            coordinates = next((n.text or '' for n in geometry if _tag_name(n.tag) == 'coordinates'), '')
            xy = []
            for raw in coordinates.split():
                try:
                    p = raw.split(',')
                    lon, lat = float(p[0]), float(p[1])
                    if math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90:
                        xy.append((lon, lat))
                except (IndexError, TypeError, ValueError):
                    continue
            if kind == 'LineString' and len(xy) >= 2:
                lines.append((name, category, xy))
            elif kind == 'Point' and xy:
                points.append((styled_name, xy[0]))
    if not lines and not points:
        raise ValueError('Tidak ada geometri titik/jalur yang terbaca pada KML/KMZ')
    return lines, points


def read_source(path):
    extension = os.path.splitext(os.fspath(path))[1].lower()
    if extension == '.kml':
        with open(path, 'rb') as f:
            return parse_kml_bytes(f.read())
    if extension == '.kmz':
        try:
            with zipfile.ZipFile(path) as package:
                names = [n for n in package.namelist() if n.lower().endswith('.kml') and not n.startswith('__MACOSX/')]
                if not names:
                    raise ValueError('Tidak ditemukan file KML dalam KMZ')
                name = next((n for n in names if n.lower() == 'doc.kml'), None)
                name = name or sorted(names, key=lambda n: (n.count('/'), len(n)))[0]
                return parse_kml_bytes(package.read(name))
        except zipfile.BadZipFile as exc:
            raise ValueError('KMZ bukan arsip yang valid') from exc
    raise ValueError('Format tidak didukung. Pilih file .kml atau .kmz')
