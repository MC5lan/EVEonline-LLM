"""本地小模型 + 确定性护栏。

模型负责说人话，护栏负责事实。三道关：

  1. 字段缺失检测（调用模型之前）
     问题问的字段不在检索结果里 → 直接答「资料里没有」，不调模型。
     35M 参数做不到「比对问题字段与 context 字段」，但代码一行就能做。

  2. 数值闭集校验（生成之后）
     回答里的每个数字必须出现在检索结果里，否则判为编造。
     实测模型会把 context 里的 9999 抄成 907，这一关能拦住。

  3. 引用回填
     复用 rag.ask 里已有的 backfill，把答案对应到具体资料来源。

用法：
  python -m rag.local_model --query "毒蜥级的护盾容量是多少"
  python -m rag.local_model --query "..." --no-guard     # 关掉护栏做对照
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 问题里可能出现的字段名，用来做「字段是否出现在资料里」的判断
FIELD_WORDS = [
    "高能量槽", "中能量槽", "低能量槽", "改装件槽", "结构值", "护盾容量",
    "装甲值", "CPU 输出", "能量栅格输出", "电容容量", "最大速度", "信号半径",
    "无人机带宽", "货舱容量", "质量", "PG 占用", "CPU 占用", "体积",
    "跃迁速度", "锁定距离", "扫描分辨率", "无人机挂舱", "最大锁定目标",
    "高槽", "中槽", "低槽", "改装件", "无人机",
]

# 资料里没有时给出的统一答复。宁可少答，也不猜。
NO_DATA = "资料里没有找到相关信息。"


def asked_field(question: str) -> str | None:
    """从问题里认出问的是哪个字段。"""
    for w in FIELD_WORDS:
        if w in question:
            return w
    return None


def field_in_context(field: str, context: str) -> bool:
    """字段名是否出现在资料里（允许「高槽/高能量槽」这类简称差异）。"""
    aliases = {
        "高槽": ["高能量槽", "高槽"], "中槽": ["中能量槽", "中槽"],
        "低槽": ["低能量槽", "低槽"], "改装件": ["改装件槽", "改装件"],
    }.get(field, [field])
    return any(a in context for a in aliases)


# 结构化字段表：和 SFT 数据生成时用的是同一份，保证格式一致
SHIP_FIELDS = [
    ("hiSlots", "高能量槽", "个"), ("medSlots", "中能量槽", "个"),
    ("lowSlots", "低能量槽", "个"), ("rigSlots", "改装件槽", "个"),
    ("hp", "结构值", "HP"), ("shieldCapacity", "护盾容量", "HP"),
    ("armorHP", "装甲值", "HP"), ("cpuOutput", "CPU 输出", "TF"),
    ("powerOutput", "能量栅格输出", "MW"), ("capacitorCapacity", "电容容量", "GJ"),
    ("maxVelocity", "最大速度", "m/s"), ("droneBandwidth", "无人机带宽", "Mbit/s"),
    # 下面这些 SDE 里本来就有，之前漏了，导致问「跃迁速度」时护栏误判为字段缺失
    ("signatureRadius", "信号半径", "m"), ("maxTargetRange", "锁定距离", "m"),
    ("scanResolution", "扫描分辨率", "mm"), ("mass", "质量", "kg"),
    ("warpSpeedMultiplier", "跃迁速度", "AU/s"),
    ("droneCapacity", "无人机挂舱", "m³"), ("maxTargets", "最大锁定目标", "个"),
    ("capacity", "货舱容量", "m³"),
]
MOD_FIELDS = [("power", "PG 占用", "MW"), ("cpu", "CPU 占用", "TF"),
              ("volume", "体积", "m³"), ("hp", "结构值", "HP"),
              ("capacity", "容量", "m³")]

# 植入体/增效剂这类也有给用户看的属性，不补就会被判「字段缺失」
EXTRA_FIELDS = [("charismaBonus", "魅力加成", ""), ("intelligenceBonus", "智力加成", ""),
                ("memoryBonus", "记忆加成", ""), ("perceptionBonus", "感知加成", ""),
                ("willpowerBonus", "意志力加成", ""), ("implantness", "植入体槽位", "个")]


def _fmt(v) -> str:
    f = float(v)
    return str(int(f)) if f.is_integer() else str(round(f, 1))


class FactContext:
    """按 SFT 训练时的紧凑格式拼 context。

    为什么不能直接用检索到的卡片：模型见到的 context 是
    「毒蜥级（Gila）：护盾容量 3200 HP；装甲值 2200 HP」这种短字段，
    而卡片是整段散文。格式对不上时它会输出乱码。
    """

    def __init__(self) -> None:
        import json
        self.ships: dict[str, dict] = {}
        path = ROOT / "data" / "sde_facts.jsonl"
        if path.exists():
            with path.open(encoding="utf-8") as f:
                for line in f:
                    o = json.loads(line)
                    if o.get("category"):
                        for key in (o.get("name_zh"), o.get("name_en")):
                            if key:
                                self.ships.setdefault(key.lower(), o)

    def find(self, question: str) -> dict | None:
        """在问题里找最长的 SDE 名称。"""
        q = question.lower()
        best = None
        for name, o in self.ships.items():
            if len(name) < 2:
                continue
            key = name[:-1] if name.endswith("级") and len(name) >= 3 else name
            if key not in q and name not in q:
                continue
            # 如果这个名字后面紧跟 I/II/III 之类罗马数字而问题里没有，
            # 说明问题问的是更具体的型号，交给更长的名字去匹配
            hit_at = q.find(name) if name in q else q.find(key)
            tail = q[hit_at + len(name): hit_at + len(name) + 3]
            if re.match(r"\s*(I{1,3}|IV|V)\b", tail) and not name.rstrip().endswith(("I", "V")):
                continue
            if best is None or len(name) > len(best[0]):
                best = (name, o)
        return best[1] if best else None

    def build(self, question: str, field: str | None) -> str | None:
        o = self.find(question)
        if not o:
            return None
        fields = (SHIP_FIELDS if o["category"] == "舰船"
                  else MOD_FIELDS + EXTRA_FIELDS)
        attrs = o.get("attributes", {})
        have = [(k, lab, u) for k, lab, u in fields if k in attrs and attrs[k]]
        if not have:
            return None
        zh = o.get("name_zh", "")
        en = o.get("name_en", "")
        # 问到的字段排在最前面，再跟两项其它字段
        want = [x for x in have if x[1] == field]
        rest = [x for x in have if x[1] != field]
        pick = (want + rest)[:3]
        head = f"{zh}（{en}）：" if en else f"{zh}："
        return head + "；".join(f"{lab} {_fmt(attrs[k])} {u}" for k, lab, u in pick)


    def find_all(self, question, limit=2):
        """问题里出现的所有实体，按出现位置排序（容忍缺「级」）。"""
        q = question.lower()
        cands = []
        for name, o in self.ships.items():
            if len(name) < 2:
                continue
            key = name[:-1] if name.endswith("级") and len(name) >= 3 else name
            pos = q.find(key)
            if pos < 0:
                continue
            cands.append((pos, len(key), o))
        cands.sort()
        out, spans = [], []
        for pos, ln, o in cands:
            # 用真实长度判重叠：之前写死 12，导致第二个实体总被当成重叠
            if any(not (pos + ln <= a or pos >= b) for a, b in spans):
                continue
            spans.append((pos, pos + ln))
            out.append(o)
            if len(out) >= limit:
                break
        return out

    def lookup(self, question, field):
        """返回 (实体名, 数值字符串, 单位)，供确定性兜底使用。

        既然 SDE 里已经有确定答案，就没必要让模型来「猜」。
        模型只在数字对得上时被采用，否则用这里的模板答案。
        """
        o = self.find(question)
        if not o or not field:
            return None
        fields = (SHIP_FIELDS if o["category"] == "舰船"
                  else MOD_FIELDS + EXTRA_FIELDS)
        attrs = o.get("attributes", {})
        for k, lab, u in fields:
            if lab == field and k in attrs and attrs[k]:
                return (o.get("name_zh", ""), _fmt(attrs[k]), u, lab)
        return None



class FitContext:
    """装配问题的 context：从 fits.jsonl 取该船那套配置的对应槽位。

    和船体属性是两回事——问「低槽装什么」，context 里必须真的有模块名，
    只给「低能量槽 4 个」它只能编。
    """

    SLOT_ZH = {"hi": "高槽", "med": "中槽", "low": "低槽",
               "rig": "改装件", "drone": "无人机", "subsystem": "子系统"}

    def __init__(self) -> None:
        import json
        self.by_ship: dict[str, dict] = {}
        path = ROOT / "data" / "fits.jsonl"
        if path.exists():
            with path.open(encoding="utf-8") as f:
                for line in f:
                    o = json.loads(line)
                    self.by_ship.setdefault(o["ship_zh"], o)

    def build(self, question: str, ship: str | None) -> str | None:
        fit = self.by_ship.get(ship or "")
        if not fit:
            return None
        groups: dict[str, list[str]] = {}
        for it in fit["items"]:
            lab = self.SLOT_ZH.get(it["slot"])
            if not lab:
                continue
            q = f"{it['qty']}x " if it.get("qty", 1) > 1 else ""
            groups.setdefault(lab, []).append(q + it["zh"])
        if not groups:
            return None
        for lab in groups:
            if lab in question:
                return f"{fit['ship_zh']}「{fit['fit']}」{lab}：{'、'.join(groups[lab])}"
        # 整套提问：必须和 SFT 训练时的 summary 格式完全一致，
        # 否则模型见到陌生格式会开始复读。
        def _slot_text(items):
            if len(items) <= 6:
                return "、".join(items)
            return "、".join(items[:6]) + f" 等 {len(items)} 件"

        summary = "；".join(f"{lab} {len(v)} 件（{_slot_text(v)}）"
                            for lab, v in groups.items())
        return f"{fit['ship_zh']}「{fit['fit']}」：{summary}"


_FIT_Q = re.compile(r"配船|配装|装配|装什么|怎么配|配置")



# 明显超出资料范围：问版本、现实世界、创作
_PRICE_Q = re.compile(r"多少钱|价格|造价|成本|值多少|能卖")

_CMP = re.compile(r"哪个|哪条|还是|对比|比较")

OOS_Q = re.compile(r"下个?版本|未来版本|现实|地球|排水量|股票|市值|写一首|作诗|诗|怎么建造|建造系统|怎么造")

# 检索最高分低于此值就当资料里没有。实测命中问题通常在 0.8 以上，
# 无关问题在 0.5 左右。
MIN_SCORE = 0.55

_SENT = re.compile(r"[^。！？\n]{4,}[。！？]?")


def extractive(hits, question, max_chars=220, n=2):
    """给资料摘录，而不是猜一句话。

    之前按词重叠挑一句，结果是碎片（「→ 卡彻星域」这种）。
    现在直接给最高分的 1~2 段原文并标注来源——用户能看出这是摘录，
    也能顺着来源去核对，比编一句更像答案。
    """
    if not hits:
        return NO_DATA
    out = []
    for h in hits[:n]:
        head = (h.get("source") or "").split(":")[-1]
        text = re.sub(r"\s+", " ", h["text"]).strip()[:max_chars]
        out.append(f"【{head}】{text}")
    return "\n\n".join(out)


class TopicIndex:
    """舰种索引 + 世界观词条的确定性查表。

    这类问题的答案本来就在我们自己建的索引文档里，让 35M 模型去读散文
    是绕远路——直接查表 100% 正确且可追溯。
    """

    def __init__(self):
        import re as _re
        self.groups = {}
        self.entities = {}
        p1 = ROOT / "canonical" / "02_舰船与装配" / "_topic_舰种索引" / "rewrite.md"
        if p1.exists():
            for m in _re.finditer(r"### (.+?)（(\d+) 艘）\n(.+)",
                                  p1.read_text(encoding="utf-8")):
                g, n, body = m.group(1), int(m.group(2)), m.group(3)
                names = [x.split("（")[0] for x in body.split("；") if x.strip()]
                self.groups[g] = (n, names)
        p2 = ROOT / "canonical" / "08_剧情与世界观" / "_topic_世界观词条索引" / "rewrite.md"
        if p2.exists():
            for m in _re.finditer(
                    r"### (.+?)\n- 全库出现 \*\*(\d+)\*\* 次(?:.*?)- 原文：「(.+?)」",
                    p2.read_text(encoding="utf-8"), _re.S):
                self.entities[m.group(1)] = (int(m.group(2)), m.group(3))

    def _entry(self, name, max_paras=2):
        p = (ROOT / "canonical" / "08_剧情与世界观" / "词条" / name / "rewrite.md")
        if not p.exists():
            return None
        paras = [x.strip() for x in p.read_text(encoding="utf-8").split("\n\n")
                 if len(x.strip()) >= 80
                 and not x.strip().startswith(("#", "分类", "以下"))]
        return "\n".join(paras[:max_paras]) if paras else None

    def answer(self, question):
        # 最长匹配优先：「枪骑兵级无畏舰」里同时含「无畏舰」
        for g, (n, names) in sorted(self.groups.items(), key=lambda kv: -len(kv[0])):
            if g not in question:
                continue
            if "几艘" in question:
                return f"{g}共 {n} 艘。"
            if "哪些" in question or "有什么船" in question:
                return f"{g}共 {n} 艘：" + "、".join(names[:10]) + "。"
        for e, (cnt, quote) in sorted(self.entities.items(), key=lambda kv: -len(kv[0])):
            if e in question and ("是什么" in question or "是什么地方" in question):
                return self._entry(e) or quote
        return None


_ASK_FIELD = re.compile(r"的(.+?)(?:是多少|多少|是什么|有多大)")


def unknown_field(question):
    """问题问的是不是我们认识的字段。

    只认 FIELD_WORDS 会漏掉没见过的词（「矿石产出速率」），
    于是护栏放行、模型编一个数。用句式抽出字段名，不认识就拒答。
    """
    m = _ASK_FIELD.search(question)
    if not m:
        return None
    cand = m.group(1).strip()
    for w in FIELD_WORDS:
        if w in cand or cand in w:
            return None
    return cand


# 常见缩写。只收高置信度的，宁缺毋滥——写错一个缩写比不答更糟。
ACRONYMS = {
    "T3C": ("战略巡洋舰", "Tech III Cruiser，可更换子系统，槽位由子系统决定"),
    "T3D": ("战略驱逐舰", "Tech III Destroyer，可切换作战模式"),
    "T2C": ("重型突击巡洋舰", "Heavy Assault Cruiser，重甲重火力巡洋舰"),
    "HAC": ("重型突击巡洋舰", "Heavy Assault Cruiser"),
    "HIC": ("重型拦截舰", "Heavy Interdictor"),
    "AF": ("突击护卫舰", "Assault Frigate"),
    "SB": ("隐形轰炸舰", "Stealth Bomber"),
    "AB": ("加力燃烧器", "Afterburner，提升最大速度"),
    "MWD": ("微型跃迁推进器", "Microwarpdrive，速度提升更大但信号半径变大"),
    "MJD": ("微型跳跃引擎", "Micro Jump Drive，向前跳跃约 100km"),
    "ECM": ("电子对抗", "Electronic Counter Measures，使目标无法锁定"),
    "ECCM": ("电子反对抗", "Electronic Counter Counter Measures，抵抗 ECM"),
    "DCU": ("损伤控制", "Damage Control，提升结构抗性"),
    "EHP": ("有效生命值", "Effective Hit Points，含抗性折算的总耐久"),
    "DPS": ("每秒伤害", "Damage Per Second"),
    "LP": ("忠诚点数", "Loyalty Points，势力战争与任务奖励"),
}


def acronym_answer(question):
    """问题里出现常见缩写时直接给定义。

    用 ASCII 字母边界而不是 \\b：中文在 Python 正则里算 word 字符，
    「T3C是什么船」的 C 后面直接接「是」，\\b 判不出边界。
    """
    hits = []
    for k, (zh, desc) in ACRONYMS.items():
        if re.search(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])", question, re.I):
            hits.append(f"{k} = {zh}（{desc}）。")
    return "\n".join(hits) if hits else None


class NumberGuard:
    """回答里的数字必须能在资料里找到。"""

    NUM = re.compile(r"\d+(?:\.\d+)?")

    def check(self, answer: str, context: str) -> list[str]:
        # 按数值比较而不是字符串：资料写「1 m³」、模型写「1.0 m³」是同一个数，
        # 字符串比对会误判成编造。
        ctx_vals = {round(float(x), 4) for x in self.NUM.findall(context)}
        bad = []
        for n in dict.fromkeys(self.NUM.findall(answer)):
            try:
                v = round(float(n), 4)
            except ValueError:
                bad.append(n)
                continue
            if v not in ctx_vals:
                bad.append(n)
        return bad


class LocalModel:
    def __init__(self, ckpt: str | Path | None = None):
        import torch
        from tokenizers import Tokenizer

        import sys
        sys.path.insert(0, str(ROOT))
        from src.model import EveLM, ModelConfig

        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else "cpu"
        ck = torch.load(ckpt or ROOT / "ckpt" / "sft.pt", map_location=self.dev)
        cfg = ModelConfig(**{k: v for k, v in ck["cfg"].items()
                             if k in ModelConfig.__dataclass_fields__})
        self.cfg = cfg
        self.m = EveLM(cfg).to(self.dev)
        self.m.load_state_dict(ck["model"])
        self.m.eval()
        self.tok = Tokenizer.from_file(str(ROOT / "tokenizer" / "tokenizer.json"))
        self.C = self.tok.token_to_id("<|context|>")
        self.U = self.tok.token_to_id("<|user|>")
        self.A = self.tok.token_to_id("<|assistant|>")
        self.E = self.tok.token_to_id("<eos>")

    def generate(self, context: str, question: str, max_new: int = 60) -> str:
        torch = self.torch
        ids = ([self.C] + self.tok.encode(context).ids
               + [self.U] + self.tok.encode(question).ids + [self.A])
        x = torch.tensor([ids], device=self.dev)
        with torch.no_grad():
            for _ in range(max_new):
                logits, _ = self.m(x[:, -self.cfg.max_seq_len:])
                nxt = int(logits[0, -1].argmax())
                if nxt == self.E:
                    break
                x = torch.cat([x, torch.tensor([[nxt]], device=self.dev)], dim=1)
        return self.tok.decode(x[0].tolist()[len(ids):]).strip()


def answer_with_guard(question: str, hits: list[dict], model: LocalModel | None,
                      use_guard: bool = True, facts: FactContext | None = None,
                      fits: "FitContext | None" = None,
                      topics: "TopicIndex | None" = None) -> dict:
    field = asked_field(question)

    # 对比题：一次给两者的关键属性，而不是只答一个
    if use_guard and facts is not None and _CMP.search(question):
        ents = facts.find_all(question, limit=2)
        if len(ents) >= 2:
            lines = []
            for o in ents:
                fs = SHIP_FIELDS if o.get("category") == "舰船" else MOD_FIELDS
                a = o.get("attributes", {})
                have = [(lab, _fmt(a[k]), u) for k, lab, u in fs if k in a and a[k]]
                lines.append("- " + o.get("name_zh", "") + "：" +
                             "；".join(f"{l} {v} {u}" for l, v, u in have[:5]))
            return {"answer": "两者的关键属性如下（资料里没有直接的取舍结论）：\n" + "\n".join(lines),
                    "blocked": None, "field": field, "numbers_bad": [], "context": ""}

    # 装配问题：只有问到具体槽位或明确说「怎么配」才走装配上下文
    ctx_fit = None
    if facts is not None and fits is not None and _FIT_Q.search(question):
        ent = facts.find(question)
        slot_words = ("高槽", "中槽", "低槽", "改装件", "无人机", "子系统")
        if ent and (any(w in question for w in slot_words)
                    or "怎么配" in question or "配船" in question):
            ctx_fit = fits.build(question, ent.get("name_zh"))

    # 属性问题：必须真的问到了字段，否则不劫持
    # （「多米尼克斯装满要多少钱」含船名但没问字段，之前被劫持成属性题）
    ctx_fact = facts.build(question, field) if (facts and field) else None
    if ctx_fit:
        context = ctx_fit
    elif ctx_fact:
        context = ctx_fact
    else:
        context = "\n".join(h["text"] for h in hits)

    # 舰种/词条类问题先查表，命中就直接答（确定性，不经过模型）
    structured = bool(ctx_fit or ctx_fact)
    # 查表不看 structured：「枪骑兵级无畏舰」里含「枪骑兵级」（一艘船），
    # FactContext 会把它认成实体，于是 structured=True 把查表挡掉了。
    if use_guard and topics is not None:
        hit = topics.answer(question)
        if hit:
            return {"answer": hit, "blocked": None, "field": field,
                    "numbers_bad": [], "context": context}

    # 缩写：T3C 这类术语直接给定义，不必靠检索
    if use_guard:
        ac = acronym_answer(question)
        if ac:
            return {"answer": ac, "blocked": None, "field": field,
                    "numbers_bad": [], "context": ""}

    # 价格类：资料里没有市场数据，直接说没有
    if use_guard and _PRICE_Q.search(question):
        return {"answer": "资料里没有价格数据（市场行情不在这个助手的范围内）。",
                "blocked": "无价格数据", "field": field,
                "numbers_bad": [], "context": ""}

    # ① 越界问题直接拒答，不调模型
    if use_guard and OOS_Q.search(question):
        return {"answer": NO_DATA, "blocked": "超出资料范围", "field": field,
                "numbers_bad": [], "context": context}

    # ② 结构化问题才有必要走模型；散文类问题直接摘原文更可靠

    # ③ 检索置信度太低（且不是结构化问题）→ 资料里没有
    if use_guard and not structured:
        top = hits[0]["score"] if hits else 0.0
        if top < MIN_SCORE:
            return {"answer": NO_DATA, "blocked": f"检索置信度低 {top:.2f}",
                    "field": field, "numbers_bad": [], "context": context}

    # ⑤ 问了一个我们不认识的字段 → 拒答（防「换个词就编」）
    if use_guard:
        uf = unknown_field(question)
        if uf and not ctx_fit:
            return {"answer": NO_DATA, "blocked": f"未知字段 {uf}",
                    "field": field, "numbers_bad": [], "context": context}

    if use_guard and field and not field_in_context(field, context):
        return {"answer": NO_DATA, "blocked": "字段缺失", "field": field,
                "numbers_bad": [], "context": context}

    # ⑤ 其余非结构化问题：结构化摘录（来源 + 最贴题的一句），不经过模型
    if use_guard and not structured:
        from rag.compose import compose
        return {"answer": compose(hits, question), "blocked": None,
                "field": field, "numbers_bad": [], "context": context}

    if model is None:
        return {"answer": "", "blocked": "无模型", "field": field, "numbers_bad": [], "context": context}

    ans = model.generate(context, question)

    # 结构化事实题：SDE 里有确定答案，模型写错了就直接用模板。
    # 模型是「措辞层」，不是「数值层」——它没有区分相似字段的能力
    # （问 PG 会抄成 CPU 的 30），那就别让它决定数字。
    if use_guard and ctx_fact and field and facts is not None:
        got = facts.lookup(question, field)
        if got:
            name, val, unit, lab = got
            have = NumberGuard.NUM.findall(ans)
            ok = any(abs(float(h) - float(val)) < 1e-6 for h in have) if have else False
            if not ok:
                return {"answer": f"{name}的{lab}是 {val} {unit}。",
                        "blocked": None, "field": field,
                        "numbers_bad": [], "context": context,
                        "fallback": True}

    if use_guard:
        bad = NumberGuard().check(ans, context)
        if bad:
            return {"answer": NO_DATA, "blocked": f"数字越界 {bad}",
                    "field": field, "numbers_bad": bad, "context": context}

    return {"answer": ans, "blocked": None, "field": field,
            "numbers_bad": [], "context": context}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--no-guard", action="store_true")
    ap.add_argument("--no-model", action="store_true")
    args = ap.parse_args()

    from rag.retriever import Retriever

    r = Retriever()
    hits = r.search(args.query, k=args.topk)
    facts = FactContext()
    fits = FitContext()
    topics = TopicIndex()
    model = None if args.no_model else LocalModel()
    res = answer_with_guard(args.query, hits, model, use_guard=not args.no_guard, facts=facts, fits=fits, topics=topics)

    print(f"\n问：{args.query}")
    print(f"资料：{[h.get('source') for h in hits]}")
    if res["blocked"]:
        print(f"⚠️  被护栏拦下：{res['blocked']}")
    print(f"答：{res['answer'] or '（空）'}")


if __name__ == "__main__":
    main()
