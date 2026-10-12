"""Prepare imported AutoCAD XDATA application registries for ODA 27.9.

Source DXF entities brought through ezdxf Importer can retain XDATA
1001 'GradientColor1ACI', 'GradientColor2ACI' or 'AcadAnnotative' while the
newly created document lacks corresponding APPID table records.
ezdxf.audit() reports 0 errors but ODA rejects this as 'Invalid RegApp'
during readFile. Register the original APPID names without modifying any
entity geometry, XDATA content, symbol, or PaperSpace layout.
"""
from collections import Counter
from ezdxf.lldxf.validator import is_valid_table_name


def ensure_xdata_regapps(document):
    """Register every referenced XDATA 1001 app name; return use counts.

    Called AFTER all native block and PaperSpace imports and BEFORE saving.
    Raises on invalid names rather than silently emitting malformed DXF.
    """
    existing={item.dxf.name.casefold() for item in document.appids}
    missing=Counter()
    for entity in document.entitydb.values():
        if not entity.is_alive:
            continue
        xdata=getattr(entity,"xdata",None)
        if not xdata:
            continue
        for name in xdata.data:
            if name.casefold() not in existing:
                if not is_valid_table_name(name):
                    raise ValueError(
                        f"Nama XDATA RegApp tidak sah: {name!r}")
                missing[name]+=1
    for name in sorted(missing,key=str.casefold):
        if name.casefold() not in existing:
            document.appids.new(name)
            existing.add(name.casefold())
    return dict(missing)


def missing_xdata_regapps(document):
    """Read-only verification for CI and diagnostic checks."""
    registered={item.dxf.name.casefold() for item in document.appids}
    return sorted({
        name for entity in document.entitydb.values() if entity.is_alive
        for name in (getattr(entity,"xdata",None).data
                     if getattr(entity,"xdata",None) else ())
        if name.casefold() not in registered
    },key=str.casefold)
