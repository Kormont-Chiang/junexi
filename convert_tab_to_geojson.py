#!/usr/bin/env python3
"""
CHGIS MapInfo TAB → GeoJSON 转换脚本
使用 fiona 直接读写
"""

import os
import json
import fiona
from fiona.transform import transform_geom

data_dir = r"C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\chgis_data"
output_dir = r"C:\Users\Lenovo\.kimi_openclaw\workspace\historia-server\chgis_data\geojson"
os.makedirs(output_dir, exist_ok=True)

tab_files = [
    ("County_Bou", "县级边界"),
    ("County_Point", "县级治所"),
    ("Prefecture_Bou", "府州边界"),
    ("Prefecture_Point", "府州治所"),
    ("Province_Bou", "省边界"),
    ("Province_Point", "省治所"),
    ("Regime_Bou", "政权边界"),
    ("Regime_Point", "政权治所"),
]

converted = []
errors = []

for name, desc in tab_files:
    tab_path = os.path.join(data_dir, f"{name}.TAB")
    if not os.path.exists(tab_path):
        errors.append(f"未找到: {name}.TAB")
        continue
    
    try:
        with fiona.open(tab_path) as src:
            schema = src.schema
            crs = src.crs
            
            print(f"  {name}: CRS={crs}, features={len(src)}, props={list(schema['properties'].keys())[:5]}")
            
            # 读取并转换坐标系到 WGS84
            records = []
            for feat in src:
                # 转换几何: Beijing 1954 (EPSG:4284) -> WGS84 (EPSG:4326)
                if crs and '4284' in str(crs):
                    new_geom = transform_geom('EPSG:4284', 'EPSG:4326', feat['geometry'])
                    feat['geometry'] = new_geom
                
                # 清理 properties 中的 None 值
                props = {}
                for k, v in feat['properties'].items():
                    if v is not None:
                        props[k] = v
                feat['properties'] = props
                
                records.append(feat)
            
            # 写入 GeoJSON
            geojson_path = os.path.join(output_dir, f"{name}.geojson")
            with fiona.open(
                geojson_path,
                'w',
                driver='GeoJSON',
                crs='EPSG:4326',
                schema=schema
            ) as dst:
                for rec in records:
                    dst.write(rec)
            
            converted.append({
                "name": name,
                "desc": desc,
                "features": len(records),
                "properties": list(schema['properties'].keys()),
                "geojson": f"chgis_data/geojson/{name}.geojson"
            })
            
            print(f"  -> OK: {geojson_path}")
            
    except Exception as e:
        errors.append(f"{name}: {str(e)}")
        print(f"  -> ERR: {e}")

# 生成索引
index = {
    "source": "CHGIS (中国历史地理信息系统)",
    "format": "GeoJSON (WGS84)",
    "converted_at": __import__('datetime').datetime.now().isoformat(),
    "layers": converted,
    "errors": errors
}

with open(os.path.join(output_dir, "index.json"), "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print(f"\n{'='*50}")
print(f"转换完成！")
print(f"GeoJSON 目录: {output_dir}")
print(f"共转换 {len(converted)} 个图层")
if errors:
    print(f"失败 {len(errors)} 个:")
    for e in errors:
        print(f"  - {e}")
