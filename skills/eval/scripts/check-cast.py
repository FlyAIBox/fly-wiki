#!/usr/bin/env python3
"""persona / scenario 自检：形状、密度、召回预览、自证预言。

    python3 check-cast.py persona.json scenario.json
    python3 check-cast.py session/                       # 递归扫目录
    python3 check-cast.py p.json --scenario s.json --target "产品名"

召回预览用的是引擎同一套打分（engine/agent/prompt.py 的 _toks/_rank），所以「哪几条经历
会浮现」是真的，不是估的。形状错 → exit 1；只有密度/召回警告 → exit 0。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

RESIDENT_BUDGET = 1200          # 超出即进渐进模式（engine._RESIDENT_BUDGET）
MEMORY_TOPK = 6
SKILL_TOPK = 4
SCENARIO_KINDS = {"task_completion", "open_exploration", "social_interaction", "evaluation_probe"}
STATUSES = {"draft", "active", "archived"}

PROFILE_MIN, PROFILE_SOFT_MAX = 300, 700
EPISODE_MIN, EPISODE_MAX = 40, 160
SKILL_TEXT_MIN, SKILL_HOOK_MAX = 60, 40
EPISODES_MIN = 3
TOTAL_MIN = 1500


def toks(s: str) -> set[str]:
    """与 engine._toks 逐字一致：英文词 + 数字 + 单个 CJK 字。"""
    return set(re.findall(r"[a-z0-9]+|[一-鿿]", (s or "").lower()))


def score(item_text: str, query: str) -> float:
    """engine._rank 的打分：|q ∩ item| / sqrt(|item|)。"""
    t = toks(item_text)
    return (len(toks(query) & t) / math.sqrt(len(t))) if t else 0.0


def episode_text(e: dict) -> str:
    return ";".join(str(e.get(k) or "") for k in ("situation", "behavior", "outcome") if e.get(k))


class Report:
    def __init__(self, label: str) -> None:
        self.label, self.errors, self.warns, self.notes = label, [], [], []

    def err(self, m: str) -> None: self.errors.append(m)
    def warn(self, m: str) -> None: self.warns.append(m)
    def note(self, m: str) -> None: self.notes.append(m)

    def render(self) -> None:
        print(f"\n=== {self.label} ===")
        for m in self.notes: print(f"  ·  {m}")
        for m in self.warns: print(f"  !  {m}")
        for m in self.errors: print(f"  ✗  {m}")
        if not self.errors and not self.warns:
            print("  ✓  形状与密度都过了")


# --------------------------------------------------------------------------- persona

def check_persona(p: dict, rep: Report, scenario: dict | None, target: str | None) -> None:
    profile = (p.get("profile") or {}).get("text") or ""
    skills = p.get("skills") or []
    memory = p.get("memory") or {}
    mem_text = memory.get("text") or ""
    episodes = memory.get("episodes") or []

    if not profile:
        rep.err("缺 profile.text")
    if not isinstance(skills, list) or not skills:
        rep.err("缺 skills")
    for i, sk in enumerate(skills):
        if not sk.get("name") or not sk.get("text"):
            rep.err(f"skills[{i}] 缺 name 或 text")
    for i, e in enumerate(episodes):
        if not e.get("situation"):
            rep.err(f"memory.episodes[{i}] 缺 situation（它是检索键，缺了这条永远不会被想起）")

    # ---- 密度
    bulk = sum(len(sk.get("text") or "") for sk in skills) + len(mem_text) \
        + sum(len(episode_text(e)) for e in episodes)
    total = len(profile) + bulk
    mode = "渐进" if bulk > RESIDENT_BUDGET else "常驻"
    rep.note(f"profile {len(profile)} 字 · skills {len(skills)} 项 · episodes {len(episodes)} 条 "
             f"· 外挂 {bulk} 字 · 合计 {total} 字 → {mode}模式")

    if len(profile) < PROFILE_MIN:
        rep.warn(f"profile {len(profile)} 字，偏薄（预算 {PROFILE_MIN}-500）——身份锚要能定住陌生情境下的取舍")
    if len(profile) > PROFILE_SOFT_MAX:
        rep.warn(f"profile {len(profile)} 字，偏厚（>{PROFILE_SOFT_MAX}）——它恒常驻，"
                 "生平搬去 memory、能力搬去 skills")
    if len(episodes) < EPISODES_MIN:
        rep.warn(f"episodes 只有 {len(episodes)} 条（建议 6-14）——可召回的具体经历太少，"
                 "行为会退回「积极的平均人」")
    if episodes and len(mem_text) > 80:
        rep.warn(f"memory.text 有 {len(mem_text)} 字，但 episodes 非空时它**完全不进模型**"
                 "（两个模式都只取 episodes）——该进模型的信息改写成 episode")
    if not (2 <= len(skills) <= 8):
        rep.warn(f"skills {len(skills)} 项，建议 2-8（宁缺毋滥，凑数会挤占目录）")
    if total < TOTAL_MIN:
        rep.warn(f"合计 {total} 字 < {TOTAL_MIN}——越过 {RESIDENT_BUDGET} 字外挂预算是目标形态，不是超标")

    for i, sk in enumerate(skills):
        t = sk.get("text") or ""
        if t and len(t) < SKILL_TEXT_MIN:
            rep.warn(f"skills[{i}] «{sk.get('name')}» 正文 {len(t)} 字偏短——写机制（怎么做到、什么效果）")
        hook = t.replace("\n", " ").split("。")[0]
        if t and len(hook) > SKILL_HOOK_MAX:
            rep.warn(f"skills[{i}] «{sk.get('name')}» 首句 {len(hook)} 字，渐进模式的目录只截前 "
                     f"{SKILL_HOOK_MAX} 字（「{hook[:SKILL_HOOK_MAX]}」）——把钩子压进第一句")

    for i, e in enumerate(episodes):
        n = len(episode_text(e))
        if n > EPISODE_MAX:
            rep.warn(f"episodes[{i}] {n} 字偏长——分母是 sqrt(词数)，长经历会稀释自己的召回分，拆成两条")
        elif 0 < n < EPISODE_MIN:
            rep.warn(f"episodes[{i}] {n} 字偏空——behavior 写真做了什么，outcome 写留下什么判断")
        if e.get("situation") and not e.get("outcome"):
            rep.warn(f"episodes[{i}] 没写 outcome——留下的判断才是它影响今天行为的通路")

    # ---- 极客锚点：具名实体（拉丁词/年份/数字）是具体度的代理指标
    body = " ".join([mem_text] + [episode_text(e) for e in episodes])
    latin = {w for w in re.findall(r"[A-Za-z][A-Za-z0-9.+#_-]{2,}", body) if len(w) > 2}
    years = set(re.findall(r"(?:19|20)\d{2}", body))
    if len(latin) < 3:
        rep.warn(f"memory 里具名实体只有 {len(latin)} 个（{'/'.join(sorted(latin)) or '无'}）——"
                 "碰工具/产品的人设要具名带版本，「熟悉某类工具」不是履历（纯人文人设可忽略这条）")
    if not years:
        rep.warn("memory 里没有年份——真实时空坐标是「像真的」的主要来源")
    if latin or years:
        rep.note(f"具名锚点：{len(latin)} 个实体、{len(years)} 个年份")

    # ---- 召回预览（引擎同一套打分）
    if scenario and episodes:
        q = " ".join([(scenario.get("goal") or {}).get("text") or "",
                      (scenario.get("env") or {}).get("text") or ""])
        ranked = sorted(((score(episode_text(e), q), i, e) for i, e in enumerate(episodes)),
                        key=lambda x: (-x[0], x[1]))
        rep.note(f"这个场景下会浮现的经历（前 {MEMORY_TOPK}；引擎同一套打分，"
                 "查询取 goal+env——实跑时还会掺入当步观察，所以这是开场时的近似）：")
        for s, i, e in ranked[:MEMORY_TOPK]:
            rep.note(f"    {s:5.2f}  [{i}] {str(e.get('situation'))[:44]}")
        cold = [i for s, i, _ in ranked[MEMORY_TOPK:] if s > 0]
        dead = [i for s, i, _ in ranked if s == 0]
        if dead:
            rep.warn(f"episodes {dead} 与本场景零词重叠，永远不会浮现——"
                     "situation 改用他将会遇到的处境的词，或换个场景用")
        elif cold:
            rep.note(f"落在前 {MEMORY_TOPK} 之外（本场景用不上，其他场景可能用得上）：{cold}")
        if skills:
            sk_ranked = sorted(((score(f"{s.get('name')} {s.get('text')}", q), i, s)
                                for i, s in enumerate(skills) if s.get("text")),
                               key=lambda x: (-x[0], x[1]))[:SKILL_TOPK]
            rep.note("会浮现的本事：" + "、".join(f"{s.get('name')}({sc:.2f})" for sc, _, s in sk_ranked))

    if target:
        hit = [seg for seg, txt in (("profile", profile), ("memory", body),
                                    ("skills", " ".join(sk.get("text") or "" for sk in skills)))
               if target.lower() in txt.lower()]
        if hit:
            rep.err(f"{hit} 里出现了被测物名「{target}」——persona 不写对被测物的看法（自证预言）")


# --------------------------------------------------------------------------- scenario

LEAK_PATTERNS = [
    (r"留意|注意看|重点关注|考察|检查一下", "像在派任务给审稿人"),
    (r"值不值得|好不好用|是否易用|评价一下|打个分|判断.{0,6}(靠不靠谱|好不好)", "把评测问题写进了轨迹"),
    (r"找茬|挑毛病|找出问题|发现缺陷|bug", "预设了要找到缺陷"),
    (r"点击|点一下|输入框|先打开.{0,10}再点|按钮", "写了操作步骤，真实摩擦就不会暴露"),
]


def check_scenario(s: dict, rep: Report, target: str | None) -> None:
    goal = (s.get("goal") or {}).get("text") or ""
    env = (s.get("env") or {}).get("text") or ""
    clo = s.get("closure") or {}

    if not goal:
        rep.err("缺 goal.text")
    if not env:
        rep.err("缺 env.text")
    kind = s.get("kind")
    if kind and kind not in SCENARIO_KINDS:
        rep.err(f"kind={kind} 不在枚举 {sorted(SCENARIO_KINDS)}")
    st = s.get("status")
    if st and st not in STATUSES:
        rep.err(f"status={st} 不在 {sorted(STATUSES)}")

    success, abandon = clo.get("success") or [], clo.get("abandon") or []
    if not success:
        rep.err("closure.success 空——没有可观察的成功证据，办成与否只能靠感觉")
    if not abandon:
        rep.warn("closure.abandon 空——这个人被写成了不会走的人，测不出流失")
    if not clo.get("max_turns"):
        rep.warn("没写 closure.max_turns——预算缺省会让它一直转")

    rep.note(f"goal {len(goal)} 字 · env {len(env)} 字 · 成功 {len(success)} 条 · 放弃 {len(abandon)} 条")
    if len(goal) < 60:
        rep.warn(f"goal {len(goal)} 字偏薄——要写清「为什么是现在」，不然只是「想试试」")
    if len(env) < 80:
        rep.warn(f"env {len(env)} 字偏薄——他手上带了什么材料、多少时间、谁在等，决定他折腾几次就走")

    body = " ".join([goal, env, clo.get("text") or ""]
                    + [c.get("text") or "" for c in success + abandon])
    for pat, why in LEAK_PATTERNS:
        m = re.search(pat, body)
        if m:
            rep.warn(f"出现「{m.group(0)}」——{why}（评测口径不进轨迹层）")
    if target and target.lower() in body.lower():
        rep.note(f"提到被测物名「{target}」——scenario 里点明入口是正常的，"
                 "只要没连带写对它的评价")


# --------------------------------------------------------------------------- 驱动

def classify(d: dict) -> str | None:
    if "profile" in d and "skills" in d:
        return "persona"
    if "goal" in d and ("closure" in d or "env" in d):
        return "scenario"
    return None


def _common_prefix(a: str, b: str) -> str:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a[:n]


def collect(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        q = Path(p)
        if q.is_dir():
            out += sorted(f for f in q.rglob("*.json") if f.name not in
                          {"bundle.json", "manifest.json", "session.json", "upload.json",
                           "case-index.json", "preflight.json", "target.json"})
        else:
            out.append(q)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="persona / scenario 自检")
    ap.add_argument("paths", nargs="+", help="json 文件或目录")
    ap.add_argument("--scenario", help="给 persona 配对的 scenario，用于召回预览")
    ap.add_argument("--target", help="被测物名字，用于自证预言检查")
    a = ap.parse_args()

    pair = json.loads(Path(a.scenario).read_text(encoding="utf-8")) if a.scenario else None

    docs: list[tuple[Path, dict, str]] = []      # (来源文件, 文档, 类型)
    reports = []
    # --scenario 既作召回预览的对照，也一起校验（否则它自己的形状与泄漏没人看）
    todo = collect(a.paths)
    if a.scenario:
        sp = Path(a.scenario)
        if not any(f.resolve() == sp.resolve() for f in todo):
            todo.append(sp)
    for f in todo:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            rep = Report(f.name)
            rep.err(f"读不了：{exc}")
            reports.append(rep)
            continue
        for d in (doc if isinstance(doc, list) else [doc]):
            if isinstance(d, dict) and (kind := classify(d)):
                docs.append((f, d, kind))

    scenarios = [(f, d) for f, d, k in docs if k == "scenario"]

    def pick_scenario(src: Path) -> dict | None:
        """给 persona 挑对照 scenario：显式 --scenario 优先，否则按文件名共同前缀配对
           （case-a-persona.json ↔ case-a-scenario.json），只有一个就用它。"""
        if pair:
            return pair
        if not scenarios:
            return None
        if len(scenarios) == 1:
            return scenarios[0][1]
        stem = src.stem
        best, best_n = None, -1
        for f, d in scenarios:
            n = len(_common_prefix(stem, f.stem))
            if n > best_n:
                best, best_n = d, n
        return best if best_n >= 4 else None

    checked = 0
    for f, d, kind in docs:
        name = d.get("name") or d.get("id") or f.name
        rep = Report(f"{kind}: {name}  ({f.name})")
        if kind == "persona":
            check_persona(d, rep, pick_scenario(f), a.target)
        else:
            check_scenario(d, rep, a.target)
        reports.append(rep)
        checked += 1

    if not checked:
        print("没找到 persona / scenario —— persona 认 profile+skills，scenario 认 goal+closure/env")
        return 1

    for r in reports:
        r.render()
    errs = sum(len(r.errors) for r in reports)
    warns = sum(len(r.warns) for r in reports)
    print(f"\n{checked} 份资产 · {errs} 个形状错 · {warns} 条密度/召回提示")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
