# 预处理 Chronas 原始数据 -> app/data/ 下的紧凑格式
# 产出:
#   provinces.json  省份多边形(坐标取2位小数)
#   entities.json   政权/文化/宗教实体表 {类型: {id: [名称, 颜色]}}
#   timeline.json   每省变更时间轴 {省名: [[年份, 政权, 文化, 宗教, 首都, 人口], ...]}
#   markers.json    标记点(名称已解码) [[id, 名称, 经度, 纬度, 类型, 起始年, 结束年], ...]
import json, os, urllib.parse, sys

SRC = '_chronas_research'
DST = 'app/data'
os.makedirs(DST, exist_ok=True)

# ---------- 1. 省份多边形 ----------
d = json.load(open(f'{SRC}/init_metadata.json', encoding='utf-8'))
feats = []
for f in d['provinces']['features']:
    name = f['properties'].get('name')
    if not name:
        continue
    geom = f['geometry']
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    simp = [[[round(x, 2), round(y, 2)] for x, y in ring] for poly in polys for ring in poly]
    feats.append([name, simp])
json.dump(feats, open(f'{DST}/provinces.json', 'w'))
print(f'provinces: {len(feats)}')

# ---------- 2. 实体表 ----------
def parse_color(v):
    if isinstance(v, str) and v.startswith('rgb('):
        return v
    if isinstance(v, str) and v.startswith('#'):
        return v
    return None

entities = {}
for typ in ('ruler', 'culture', 'religion', 'religionGeneral'):
    tbl = {}
    for k, v in d[typ].items():
        name, color = v[0], parse_color(v[1])
        if not color:  # 无色则按 id 稳定散列一个
            h = hash(k) & 0xFFFFFF
            color = f'#{h:06x}'
        tbl[k] = [name, color]
    entities[typ] = tbl
json.dump(entities, open(f'{DST}/entities.json', 'w'), ensure_ascii=False)
print(f"entities: ruler={len(entities['ruler'])} culture={len(entities['culture'])} "
      f"religion={len(entities['religion'])}")

# ---------- 3. 年度快照 -> 变更时间轴 ----------
timeline = {}
prev = {}
years = [y for y in os.listdir(f'{SRC}/areas')
         if y.endswith('.json') and y != '_errors.json']
years.sort(key=lambda fn: int(fn[:-5]))  # 必须按年份数值排序,不能按文件名字符串
for i, fn in enumerate(years):
    year = int(fn[:-5])
    area = json.load(open(f'{SRC}/areas/{fn}', encoding='utf-8'))
    for prov, val in area.items():
        val = val[:5]
        if prov not in prev or prev[prov] != val:
            timeline.setdefault(prov, []).append([year] + val)
            prev[prov] = val
    if (i + 1) % 1000 == 0:
        print(f'  areas processed {i+1}/{len(years)}', flush=True)
json.dump(timeline, open(f'{DST}/timeline.json', 'w'), ensure_ascii=False)
sz = os.path.getsize(f'{DST}/timeline.json') / 1024 / 1024
print(f'timeline: {len(timeline)} provinces, {sz:.1f} MB')

# ---------- 4. 标记点 ----------
markers = []
for m in json.load(open(f'{SRC}/all_markers.json', encoding='utf-8')):
    coo = m.get('coo')
    if not coo:
        continue
    name = m.get('name', '')
    try:
        name = urllib.parse.unquote(name)
    except Exception:
        pass
    markers.append([m['_id'], name, coo[0], coo[1], m.get('type', ''),
                    m.get('year'), m.get('end')])
json.dump(markers, open(f'{DST}/markers.json', 'w'), ensure_ascii=False)
print(f'markers: {len(markers)}, '
      f'{os.path.getsize(f"{DST}/markers.json")/1024/1024:.1f} MB')
print('DONE')
