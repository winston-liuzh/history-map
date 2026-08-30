# -*- coding: utf-8 -*-
"""
build_archaeology.py — 把考古文化层(archaeology.json)合并进 timeline.json / entities.json,
并生成 data/sources.json(数据来源标识, 前端展示用)。

设计:
- 只填充"空白省份": 首条有效记录(政权/文化/宗教任一非空) >= 1年 或完全没有有效记录的省。
  已有前公元数据(即使有错)的省份不动, 由人工另行修正。
- 记录格式沿用 chronas 的 [年份, 政权, 文化, 宗教, 首都, 人口], 追加第7位 = 来源id。
  原有记录不含第7位, 前端按缺省视为 chronas。
- 幂等: 重跑前先剥离全部带第7位的旧插入记录, 再重新插入。
用法: python build_archaeology.py   (在 app/ 目录下, 依赖 data/provinces.json + timeline.json)
"""
import json, os

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

def load(name):
    with open(os.path.join(D, name), encoding='utf-8') as f:
        return json.load(f)

def save(name, obj):
    with open(os.path.join(D, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))

provinces = load('provinces.json')   # [[name, rings...], ...]
timeline = load('timeline.json')     # {prov: [[year, ruler, culture, religion, capital, pop(, src)], ...]}
entities = load('entities.json')     # {ruler/culture/religion: {id: [name, color]}}
arch = load('archaeology.json')

def centroid(rings):
    r = max(rings, key=len)
    lon = sum(p[0] for p in r) / len(r)
    lat = sum(p[1] for p in r) / len(r)
    return lon, lat

CENT = {p[0]: centroid(p[1]) for p in provinces}

def first_real_year(recs):
    for x in recs:
        if x[1] or x[2] or x[3]:
            return x[0]
    return None

# ---------- 1. 幂等: 剥离旧的考古插入记录(带第7位来源字段) ----------
stripped = 0
for p, recs in timeline.items():
    kept = [r for r in recs if len(r) <= 6]
    stripped += len(recs) - len(kept)
    timeline[p] = kept

# ---------- 2. 逐层插入 ----------
report = []
for layer in arch['layers']:
    lid, start, end = layer['id'], layer['start'], layer['end']
    lon0, lon1, lat0, lat1 = layer['region']
    filled = []
    for p, (lon, lat) in CENT.items():
        if not (lon0 <= lon <= lon1 and lat0 <= lat <= lat1):
            continue
        recs = timeline.get(p)
        if recs is None:
            continue
        fy = first_real_year(recs)
        if fy is not None and fy < 1:
            continue  # 公元前已有数据, 不动
        # 有效起点: 必须早于该省首条有效记录(若有)
        eff_start = start
        if fy is not None and start >= fy:
            continue
        existing_years = {r[0] for r in recs}
        changed = False
        # 起点: 同年已有"全空"占位记录则原位改写; 有内容则跳过
        def fields():
            if layer.get('field') == 'ruler':
                return [lid, layer.get('culture_id', ''), '', '', 0, 'arch']
            return ['', lid, '', '', 0, 'arch']
        hit = next((r for r in recs if r[0] == start), None)
        if hit is not None:
            if not (hit[1] or hit[2] or hit[3]):
                hit[1:7] = fields()   # 原位改写空占位记录
                changed = True
        elif start not in existing_years:
            recs.append([start] + fields())
            changed = True
        # 文化层在其学界终点早于公元1年时, 插入'重置'记录 → 回归无记载
        if end < 1 and (fy is None or end < fy) and end != start:
            hit_end = next((r for r in recs if r[0] == end), None)
            if hit_end is None:
                recs.append([end, '', '', '', '', 0, 'arch'])
                changed = True
        if changed:
            timeline[p] = sorted(recs, key=lambda r: r[0])
            filled.append(p)
    # 实体表登记
    if layer.get('field') == 'ruler':
        entities.setdefault('ruler', {})[lid] = [layer['name'], layer['color']]
        if layer.get('culture_id'):
            entities.setdefault('culture', {})[layer['culture_id']] = [layer['culture_name'], layer['color']]
    else:
        entities.setdefault('culture', {})[lid] = [layer['name'], layer['color']]
    report.append((layer['name'], len(filled), filled[:5]))

# ---------- 3. 生成 sources.json(来源标识) ----------
sources = {
    'chronas': {
        'name': 'Chronas / 英文维基百科',
        'type': '政治史 · 众包', 'license': 'CC BY-SA'
    }
}
for sid, s in arch['sources'].items():
    sources[sid] = {
        'name': s['name'], 'type': '考古学文化 · 整理',
        'desc': s.get('desc', ''), 'refs': s.get('refs', []),
        'layers': {l['id']: {'name': l['name'], 'note': l['note'],
                             'span': f'{l["start"]} ~ {l["end"]}'}
                   for l in arch['layers'] if l.get('field') != 'ruler' or sid == 'arch'}
    }
save('sources.json', sources)

save('timeline.json', timeline)
save('entities.json', entities)

print(f'剥离旧插入 {stripped} 条')
total = 0
for name, n, sample in report:
    total += n
    print(f'{name}: {n} 省 {sample}')
print(f'共填充 {total} 省; timeline 记录总数 {sum(len(v) for v in timeline.values())}')
