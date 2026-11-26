# -*- coding: utf-8 -*-
"""
director.assets — 素材登记表

EDL 要求镜头用 id 引用素材，且每个素材必须有 license 与 source_url。
这个表负责去重登记，避免手写重复条目。
"""


class AssetTable:
    def __init__(self):
        self.items = []

    def add(self, aid, src, caption="", license="public-domain",
            source_url="https://images.nasa.gov"):
        for a in self.items:
            if a["id"] == aid:
                return aid
        self.items.append({"id": aid, "kind": "archive", "src": src,
                           "license": license, "source_url": source_url,
                           "caption": caption})
        return aid

    def has(self, aid):
        return any(a["id"] == aid for a in self.items)

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)
