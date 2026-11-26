#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_assets.py — 从 NASA 图库抓公有领域素材

用法:
    python fetch_assets.py --out ../assets/nasa

设计要点：
  * 只用 NASA 官方图库 API（images-api.nasa.gov），全部为公有领域
  * 每个查询带重试（网络不稳）
  * 下载 large.jpg，保留 nasa_id 与官方页 URL 写进 manifest.json
"""
import json, os, sys, time, argparse, urllib.request, urllib.parse, urllib.error

API = "https://images-api.nasa.gov"
UA = {"User-Agent": "Mozilla/5.0 film-engine/1.0"}

# (查询词, 文件名, 标题里必须出现的关键词列表, 官方页 id 前缀约束)
QUERIES = [
    ("voyager 1 launch 1977",            "01-launch",        ["launch"],        None),
    ("voyager golden record",            "02-record",        ["record"],        None),
    ("voyager spacecraft",               "03-spacecraft",    ["voyager"],       None),
    ("jupiter great red spot",           "04-jupiter",       ["jupiter"],       None),
    ("voyager saturn rings",             "05-saturn",        ["saturn"],        None),
    ("uranus voyager",                   "06-uranus",        ["uranus"],        None),
    ("neptune voyager",                  "07-neptune",       ["neptune"],       None),
    ("pale blue dot",                    "08-pale-blue-dot", ["pale"],          None),
    ("heliopause artist concept",        "09-heliopause",    ["helio"],         None),
    ("voyager interstellar space",       "10-interstellar",  ["interstellar"],  None),
    ("earth from space",                 "11-earth",         ["earth"],         None),
]


def get(url, tries=4, timeout=30):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def search(q, page_size=8):
    url = f"{API}/search?q={urllib.parse.quote(q)}&media_type=image&page_size={page_size}"
    return json.loads(get(url).decode("utf-8", "ignore"))["collection"]["items"]


def pick(items, keywords):
    for it in items:
        d = it["data"][0]
        t = (d.get("title") or "").lower()
        if all(k in t for k in keywords):
            return d
    for it in items:                       # 退而求其次
        return it["data"][0]
    return None


def manifest(nasa_id):
    url = f"{API}/asset/{nasa_id}"
    items = json.loads(get(url).decode("utf-8", "ignore"))["collection"]["items"]
    for want in ("~large.jpg", "~medium.jpg", "~orig.jpg"):
        for it in items:
            if it["href"].endswith(want):
                return it["href"]
    return items[0]["href"] if items else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../assets/nasa")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)

    manifest_path = os.path.join(out, "manifest.json")
    records = []
    if os.path.exists(manifest_path):
        records = json.load(open(manifest_path, encoding="utf-8"))
    have = {r["file"] for r in records}

    for q, fname, kws, _ in QUERIES:
        target = f"{fname}.jpg"
        if target in have:
            print(f"[skip] {target}")
            continue
        try:
            items = search(q)
            d = pick(items, kws)
            if not d:
                print(f"[miss] {q}")
                continue
            href = manifest(d["nasa_id"])
            if not href:
                print(f"[miss-url] {q}")
                continue
            data = get(href, tries=5, timeout=60)
            p = os.path.join(out, target)
            with open(p, "wb") as f:
                f.write(data)
            rec = {
                "file": target,
                "id": d["nasa_id"],
                "title": d.get("title"),
                "page": f"https://images.nasa.gov/details/{d['nasa_id']}",
                "license": "public-domain",
                "bytes": len(data),
            }
            records.append(rec)
            have.add(target)
            print(f"[ok] {target:22s} {len(data)//1024:5d} KB  {d.get('title')}")
        except Exception as e:
            print(f"[fail] {q}: {e}")

    json.dump(records, open(manifest_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n共 {len(records)} 条，manifest: {manifest_path}")


if __name__ == "__main__":
    main()
