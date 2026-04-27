"""
M0.4 主持人 + 编排控制器

按 M0.3 设计：
- crisis=true → 危机分支（不调用 3 agent）
- needs_followup=true → 追问分支（不调用 3 agent）
- intent=listen → 苏轼首发模式（跳过互驳）
- intent=decision/advice → 2 轮深度辩论 + 综合输出

总共 5 个 stage 串行：首发 → 第1轮反驳+回应 → 第2轮反驳+回应。
每 stage 内 3 次 LLM 调用并行（concurrent.futures）。
"""

from __future__ import annotations

import yaml
import concurrent.futures
from pathlib import Path

from router import route
from agents import PERSONAS, _call_llm
import corpus_loader

HERE = Path(__file__).parent

# ============= 4 个主持人 prompt（内置常量） =============

CRISIS_PROMPT = """你是「职场三人智囊团」的主持人。

刚才用户的输入触发了危机信号。
你的任务：
1. 直接引用用户原话里的关键词（让用户感到被听见）
2. 不诊断、不评判、不让 3 个角色 agent 发言
3. 列出全国心理援助热线 + 北京危机干预中心电话
4. 邀请用户去家人/朋友身边
5. 保留对话空间——不让用户感到被推走

不要：
- 不要说"你不要这样想"
- 不要说"我理解你"——你不是人，别假装
- 不要给"5 个缓解焦虑的方法"

【输出格式】
直接 markdown 文本，200-300 字。不要 YAML，不要代码块标记。
温暖但克制，不煽情。

【参考模板】

看到你说的话，我们停一停。

刚才你说的"{crisis_reason 里的具体词}"，
不像是只是工作的事。

如果你只是太累了，可以告诉我，我们慢慢来。
但如果你有伤害自己的念头，请现在就拨打：
- 全国心理援助热线：400-161-9995
- 北京心理危机研究与干预中心：010-82951332

不论你现在是什么状态，先放下手机，到家人或朋友身边。
我们之后再谈工作的事。
"""


FOLLOWUP_PROMPT = """你是「职场三人智囊团」的主持人。

Router 判定信息不齐，需要先追问用户。
你的任务：
用主持人语气把 followup_questions 包装一下，问回用户。

模板：
"你说的【一句用户原话片段】，我们三个想再听清楚一件事——
{followup_questions[0]}
（如果有第 2 个，也问，但不要超过 2 个）
不必详细，你方便说多少都行。"

【输出格式】
直接 markdown 文本，80-150 字。不要 YAML，不要代码块标记。
"""


SYNTHESIZE_PROMPT = """你是「职场三人智囊团」的主持人。

【你的角色】
你不是第 4 个角色，你是产品声音。
- 不要有"我"的立场
- 不要把 3 人观点调和成 1 个
- 让用户在 3 人观点之间自己选

【你的任务】
按以下结构输出 markdown：
1. opening：1-2 句，引用用户原话片段
2. 3 人发言精炼版（每人 120-180 字）——保留每人标志性句子（曾的"日课"、苏的诗词、王的 mirror_question）
3. 他们吵了 2 轮（折叠展开式列出 12 条交锋，每条 25-50 字）
4. 主持人综合：consensus（一致点）+ disagreement（分歧点，至少 2 条）
5. 最小一件事：今晚做什么（必须可执行，禁止"调整心态"，**严禁"30 天/60 天/90 天"等长期承诺**——只要近期可立刻验证的一件事）
6. closing_question：用王阳明的 mirror_question 原文收尾

【铁律】
- 主持人不站队
- minimum_action 必须可执行
- 移除任何不在三人语料库里的引文（已被自动 flag）
- 总字数 800-1500 字（不含 debate 折叠区）
- 如果上下文里 `confidence_warning_required: true`，必须在 opening 后加一句：
  "（你提供的信息有限，以下三人发言基于现有线索，仅供参考。）"
- ⚠️ **严禁引用用户未提及的具体细节**：如果上游 agent 输出里出现了用户未说过的月薪数字、城市、家庭关系、年龄等——必须**移除或改写**，绝不在主持人综合里复述。只能复述 router_card.fact_reconstruction 里真实出现的事实

【输出格式】
markdown，可读性优先，不要 YAML，不要代码块标记。
"""


FALLBACK_PROMPT = """你是「职场三人智囊团」的主持人。

今天 3 人智囊团里有人没能发言（YAML 失败/编造问题/超时）。

你的任务：
1. 用一句话告诉用户"今天三人状态不齐"
2. 把成功发言的 agent 输出简化呈现
3. 邀请用户：可以再描述一下情况，让其他声音进来
4. 不要假装 3 人都发言了

【输出格式】
markdown 文本，200-400 字。不要 YAML，不要代码块标记。
"""


# ============= 配对设计 =============

ROUND_1_PAIRS = [("曾国藩", "苏轼"), ("苏轼", "王阳明"), ("王阳明", "曾国藩")]
ROUND_2_PAIRS = [("曾国藩", "王阳明"), ("王阳明", "苏轼"), ("苏轼", "曾国藩")]


# ============= Moderator =============

class Moderator:

    def handle(self, user_input: str) -> dict:
        """主入口：返回 {output_type, text, debug}"""
        card = route(user_input)

        if card.get("crisis"):
            return self._crisis_response(card)

        if card.get("needs_followup"):
            return self._followup_question(card)

        intent = (card.get("core") or {}).get("intent", "decision")
        if intent == "listen":
            return self._listen_flow(card)

        return self._decision_flow(card)

    # ---------- 危机分支 ----------
    def _crisis_response(self, card: dict) -> dict:
        user_msg = (
            f"crisis_reason: {card.get('crisis_reason', '')}\n"
            f"用户原话片段: {(card.get('fact_reconstruction') or {}).get('objective', '')}"
        )
        text = _call_llm(CRISIS_PROMPT, user_msg, max_tokens=600)
        return {
            "output_type": "crisis_response",
            "text": text,
            "agents_consulted": [],
            "debug": {"router_card": card},
        }

    # ---------- 追问分支 ----------
    def _followup_question(self, card: dict) -> dict:
        user_msg = (
            f"用户原话: {(card.get('fact_reconstruction') or {}).get('objective', '')}\n"
            f"followup_questions: {card.get('followup_questions', [])}"
        )
        text = _call_llm(FOLLOWUP_PROMPT, user_msg, max_tokens=400)
        return {
            "output_type": "followup_question",
            "text": text,
            "questions": card.get("followup_questions", []),
            "agents_consulted": [],
            "debug": {"router_card": card},
        }

    # ---------- listen 流程 ----------
    def _listen_flow(self, card: dict) -> dict:
        opinions = self._parallel_first_opinions(card)
        text = self._synthesize_listen(card, opinions)
        return {
            "output_type": "full_response",
            "intent": "listen",
            "text": text,
            "agents_consulted": ["苏轼", "曾国藩", "王阳明"],
            "debug": {"router_card": card, "opinions": opinions},
        }

    # ---------- decision/advice 流程：2 轮辩论 ----------
    def _decision_flow(self, card: dict) -> dict:
        print("[moderator] Stage 0: 3 人并行首发...")
        opinions = self._parallel_first_opinions(card)

        print("[moderator] Stage 1.1: 第 1 轮反驳（顺时针）...")
        rebuttals_r1 = self._parallel_rebuttals(card, ROUND_1_PAIRS, opinions, round_num=1)

        print("[moderator] Stage 1.2: 第 1 轮回应...")
        replies_r1 = self._parallel_replies(card, ROUND_1_PAIRS, opinions, rebuttals_r1, round_num=1)

        print("[moderator] Stage 2.1: 第 2 轮反驳（逆时针）...")
        rebuttals_r2 = self._parallel_rebuttals(
            card, ROUND_2_PAIRS, opinions, round_num=2, peer_replies=replies_r1
        )

        print("[moderator] Stage 2.2: 第 2 轮回应...")
        replies_r2 = self._parallel_replies(card, ROUND_2_PAIRS, opinions, rebuttals_r2, round_num=2)

        flagged = self._verify_references(opinions)

        print("[moderator] Synthesize: 主持人综合...")
        text = self._synthesize_decision(
            card, opinions, rebuttals_r1, replies_r1, rebuttals_r2, replies_r2, flagged
        )

        return {
            "output_type": "full_response",
            "intent": (card.get("core") or {}).get("intent"),
            "text": text,
            "agents_consulted": ["曾国藩", "苏轼", "王阳明"],
            "debug": {
                "router_card": card,
                "opinions": opinions,
                "round_1": {"rebuttals": rebuttals_r1, "replies": replies_r1},
                "round_2": {"rebuttals": rebuttals_r2, "replies": replies_r2},
                "fabricated_quotes_flagged": flagged,
            },
        }

    # ---------- 并行调度 ----------
    def _parallel_first_opinions(self, card: dict) -> dict:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = {p: ex.submit(PERSONAS[p].first_opinion, card) for p in PERSONAS}
            return {p: f.result() for p, f in futures.items()}

    def _parallel_rebuttals(
        self,
        card: dict,
        pairs: list,
        opinions: dict,
        round_num: int,
        peer_replies: dict | None = None,
    ) -> dict:
        def task(speaker: str, target: str):
            adj_r1 = peer_replies.get(target) if peer_replies else None
            return PERSONAS[speaker].rebuttal(
                router_card=card,
                target=target,
                peer_first=opinions[target],
                round_num=round_num,
                peer_adjust_round1=adj_r1,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = {(s, t): ex.submit(task, s, t) for s, t in pairs}
            return {pair: f.result() for pair, f in futures.items()}

    def _parallel_replies(
        self,
        card: dict,
        pairs: list,
        opinions: dict,
        rebuttals: dict,
        round_num: int,
    ) -> dict:
        def task(speaker: str, target: str):
            return PERSONAS[target].adjust(
                router_card=card,
                my_first=opinions[target],
                trigger=rebuttals[(speaker, target)],
                round_num=round_num,
                triggered_by="peer_rebuttal",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = {t: ex.submit(task, s, t) for s, t in pairs}
            return {target: f.result() for target, f in futures.items()}

    # ---------- 引文核验 ----------
    def _verify_references(self, opinions: dict) -> list:
        """扫描 3 人首发的 references，返回未在语料库的伪引用列表。"""
        flagged = []
        for persona, op in opinions.items():
            refs = op.get("references") or []
            if not isinstance(refs, list):
                continue
            for r in refs:
                if not isinstance(r, dict):
                    continue
                quote_text = r.get("quote", "")
                ok, _ = corpus_loader.verify_quote(persona, quote_text)
                if not ok and quote_text:
                    flagged.append({
                        "persona": persona,
                        "quote": quote_text,
                        "claimed_source": r.get("source", ""),
                    })
        return flagged

    # ---------- 综合输出 ----------
    def _synthesize_decision(
        self,
        card: dict,
        opinions: dict,
        rebuttals_r1: dict,
        replies_r1: dict,
        rebuttals_r2: dict,
        replies_r2: dict,
        flagged: list,
    ) -> str:
        score = card.get("score", 0) or 0
        context = {
            "router_card": card,
            "opinions": opinions,
            "round_1": {
                "rebuttals": {f"{s}->{t}": v for (s, t), v in rebuttals_r1.items()},
                "replies": replies_r1,
            },
            "round_2": {
                "rebuttals": {f"{s}->{t}": v for (s, t), v in rebuttals_r2.items()},
                "replies": replies_r2,
            },
            "fabricated_quotes_to_remove": flagged,
            "confidence_warning_required": score < 50,
        }
        ctx_yaml = yaml.dump(context, allow_unicode=True, sort_keys=False)
        if len(ctx_yaml) > 30000:
            ctx_yaml = ctx_yaml[:30000] + "\n...（已截断）"

        return _call_llm(SYNTHESIZE_PROMPT, ctx_yaml, max_tokens=4096)

    def _synthesize_listen(self, card: dict, opinions: dict) -> str:
        context = {
            "router_card": card,
            "intent": "listen",
            "opinions": opinions,
            "instruction": "用户在倾诉。按 listen 模板：苏轼完整首发为主体，曾/王 各 1 句补位。不展示 debate。",
        }
        ctx_yaml = yaml.dump(context, allow_unicode=True, sort_keys=False)
        return _call_llm(SYNTHESIZE_PROMPT, ctx_yaml, max_tokens=2048)


if __name__ == "__main__":
    print("[moderator] self-test: import 检查")
    m = Moderator()
    print(f"  PERSONAS: {list(PERSONAS.keys())}")
    print(f"  ROUND_1: {ROUND_1_PAIRS}")
    print(f"  ROUND_2: {ROUND_2_PAIRS}")
    print("✅ moderator 模块加载正常")
