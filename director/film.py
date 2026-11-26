# -*- coding: utf-8 -*-
"""
director.film — 影片对象：加载 / 修改 / 保存 EDL，处理时间轴

EDL 是唯一契约，其余模块（渲染、质检、音频）都只读它。
"""
import json
import os


class Film:
    def __init__(self, edl, path=None):
        self.edl = edl
        self.path = path

    # ---------- 读写 ----------
    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), path)

    def save(self, path=None):
        p = path or self.path
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.edl, f, ensure_ascii=False, indent=2)
        self.path = p
        return p

    # ---------- 查询 ----------
    @property
    def shots(self):
        return self.edl["shots"]

    @property
    def duration(self):
        return self.edl["meta"]["duration"]

    def shot(self, sid):
        for s in self.shots:
            if s["id"] == sid:
                return s
        raise KeyError(sid)

    def act(self, aid):
        for a in self.edl["acts"]:
            if a["id"] == aid:
                return a
        raise KeyError(aid)

    def total(self):
        return sum(s["t1"] - s["t0"] for s in self.shots)

    # ---------- 时间轴 ----------
    def retime(self, start=0.0):
        """按顺序无缝排布，保留每镜时长"""
        t = start
        for s in self.shots:
            dur = s["t1"] - s["t0"]
            s["t0"], s["t1"] = round(t, 3), round(t + dur, 3)
            t += dur
        self.edl["meta"]["duration"] = round(t, 3)
        return self

    def rebase_acts(self):
        """按镜头归属重算幕的起止"""
        for a in self.edl["acts"]:
            ts = [(s["t0"], s["t1"]) for s in self.shots if s.get("act") == a["id"]]
            if ts:
                a["t0"] = min(t for t, _ in ts)
                a["t1"] = max(u for _, u in ts)
        return self

    def finalize(self):
        """收尾：重排时间轴、重算幕边界、写总时长"""
        self.retime()
        self.rebase_acts()
        self.edl["meta"]["duration"] = round(self.total(), 3)
        return self

    # ---------- 增删 ----------
    def add(self, shot):
        self.shots.append(shot)
        self.shots.sort(key=lambda s: s["t0"])
        return shot

    def add_many(self, shots):
        for s in shots:
            self.add(s)
        return self

    def remove(self, sid):
        self.edl["shots"] = [s for s in self.shots if s["id"] != sid]
        return self

    def replace(self, sid, shot):
        for i, s in enumerate(self.shots):
            if s["id"] == sid:
                self.shots[i] = shot
                return self
        raise KeyError(sid)

    # ---------- 校验辅助 ----------
    def ids(self):
        return [s["id"] for s in self.shots]

    def check_continuity(self):
        """返回时间轴缝隙与重叠"""
        issues = []
        for a, b in zip(self.shots, self.shots[1:]):
            gap = round(b["t0"] - a["t1"], 3)
            if abs(gap) > 0.01:
                issues.append((a["id"], b["id"], gap))
        return issues

    def __repr__(self):
        return f"<Film {self.edl['meta'].get('title')} {len(self.shots)}镜 {self.total():.0f}s>"
