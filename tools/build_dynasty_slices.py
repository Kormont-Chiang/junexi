# -*- coding: utf-8 -*-
"""按朝代窗口切分 CHGIS 时间序列（省/府两级），简化后输出 per-dynasty GeoJSON。

数据源: chgis_data/geojson/Prefecture_Bou.geojson (2016 features, -224..1911)
        chgis_data/geojson/Province_Bou.geojson   (489 features, 188..1911)
输出:   chgis_data/dynasty_<key>.geojson  （RANK: 1=一级政区 2=二级政区）

纯标准库。窗口为 circa 该朝存续期，filter = 与窗口有交集的记录。
"""
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "chgis_data", "geojson")
OUT = os.path.join(BASE, "chgis_data")

EPS = 0.004  # 约 400m 简化容差

WINDOWS = {
    "qin": (-221, -206),
    "han_west": (-202, 8),
    "han_east": (25, 220),
    "wei": (220, 266),
    "shu": (221, 263),
    "wu": (222, 280),
    "jin_west": (266, 316),
    "jin_east": (317, 420),
    "southern_northern": (420, 589),
    "sui": (581, 618),
    "tang": (618, 907),
    "five_dynasties": (907, 960),
    "song_north": (960, 1127),
    "song_south": (1127, 1279),
    "yuan": (1271, 1368),
    "ming": (1368, 1644),
    "qing": (1644, 1911),
}

KEEP_PROPS = ["NAME_CH", "NAME_PY", "TYPE_CH", "BEG_YR", "END_YR", "PRES_LOC"]


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    x1, y1 = pts[0]
    x2, y2 = pts[-1]
    dx, dy = x2 - x1, y2 - y1
    denom = (dx * dx + dy * dy) ** 0.5 or 1e-12
    idx, dmax = 0, 0.0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / denom
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        left = rdp(pts[: idx + 1], eps)
        right = rdp(pts[idx:], eps)
        return left[:-1] + right
    return [pts[0], pts[-1]]


def simplify_ring(ring):
    pts = [list(p) for p in ring]
    closed = pts[0] == pts[-1]
    body = pts[:-1] if closed else pts
    out = rdp(body, EPS)
    if len(out) < 4:
        return None
    if closed:
        out = out + [out[0]]
    return out


def simplify_geom(geom):
    if not geom:
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon":
        polys = [coords]
    else:  # MultiPolygon（及未知类型按 MultiPolygon 处理）
        polys = coords
    new_polys = []
    for poly in polys:
        if not poly:
            continue
        new_rings = []
        for ring in poly:
            r = simplify_ring(ring)
            if r:
                new_rings.append(r)
        if new_rings:
            new_polys.append(new_rings)
    if not new_polys:
        return None
    if gtype == "Polygon":
        return {"type": "Polygon", "coordinates": new_polys[0]}
    return {"type": "MultiPolygon", "coordinates": new_polys}


def load(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return json.load(f)["features"]


def main():
    layers = [(load("Province_Bou.geojson"), 1), (load("Prefecture_Bou.geojson"), 2)]
    for key, (beg, end) in WINDOWS.items():
        feats = []
        for src_feats, rank in layers:
            for f in src_feats:
                p = f.get("properties", {})
                fb, fe = p.get("BEG_YR"), p.get("END_YR")
                if fb is None or fe is None:
                    continue
                if fe < beg or fb > end:
                    continue
                geom = simplify_geom(f["geometry"])
                if not geom:
                    continue
                props = {k: p.get(k) for k in KEEP_PROPS if p.get(k) not in (None, "")}
                props["RANK"] = rank
                feats.append({"type": "Feature", "properties": props, "geometry": geom})
        path = os.path.join(OUT, f"dynasty_{key}.geojson")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False)
        mb = os.path.getsize(path) / 1e6
        print(f"{key:20s} window {beg:>5}..{end:>5}  features {len(feats):4d}  {mb:6.2f} MB")


if __name__ == "__main__":
    main()
