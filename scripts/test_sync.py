from sync_products import parse_rows

HEADER = [[""] * 32, [""] * 32]


def row(name, slots):
    """slots: list of (sku_col, satuan_col, isi_col_or_None, sku, satuan, isi)"""
    r = [""] * 32
    r[0], r[2], r[3] = "Kresek", "Taxi", name
    for sku_col, sat_col, isi_col, sku, sat, isi in slots:
        r[sku_col], r[sat_col] = sku, sat
        if isi_col is not None:
            r[isi_col] = isi
    return r


def test_multi_satuan_mult():
    vals = HEADER + [row("Kresek Taxi 15", [
        (28, 6, None, "SKU-BAL", "Bal (20 Ikat)", ""),
        (30, 10, 9, "SKU-IKAT", "Ikat (10 Pack)", "20"),
        (31, 12, 11, "SKU-PACK", "Pack", "200"),
    ])]
    products, skipped, dupes = parse_rows(vals)
    by = {p["sku"]: p for p in products}
    assert by["SKU-BAL"]["mult"] == 200
    assert by["SKU-IKAT"]["mult"] == 10
    assert by["SKU-PACK"]["mult"] == 1
    assert by["SKU-BAL"]["unit_order"] == 0
    assert by["SKU-PACK"]["unit_order"] == 3


def test_satuan_tunggal():
    vals = HEADER + [row("Mika DP 7C", [(28, 6, None, "SKU-M", "Pack", "")])]
    products, _, _ = parse_rows(vals)
    assert products[0]["mult"] == 1


def test_isi_rusak_fallback_1():
    vals = HEADER + [row("Aneh", [
        (28, 6, None, "SKU-X", "Dus", ""),
        (29, 8, 7, "SKU-Y", "Pcs", "abc"),
    ])]
    products, _, _ = parse_rows(vals)
    by = {p["sku"]: p for p in products}
    assert by["SKU-X"]["mult"] == 1
    assert by["SKU-Y"]["mult"] == 1


def test_skip_tanpa_satuan_dan_dupe():
    vals = HEADER + [
        row("A", [(28, 6, None, "SKU-1", "", "")]),
        row("B", [(28, 6, None, "SKU-2", "Pack", "")]),
        row("C", [(28, 6, None, "SKU-2", "Pack", "")]),
    ]
    products, skipped, dupes = parse_rows(vals)
    assert len(products) == 1 and skipped == 1 and dupes == 1


def test_angka_indonesia():
    vals = HEADER + [row("D", [
        (28, 6, None, "SKU-G", "Bal", ""),
        (29, 8, 7, "SKU-P", "Pcs", "1.000"),
    ])]
    products, _, _ = parse_rows(vals)
    by = {p["sku"]: p for p in products}
    assert by["SKU-G"]["mult"] == 1000
