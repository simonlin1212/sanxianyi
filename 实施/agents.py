"""
M0.4 三个 agent 包装类

每个 agent 通过 system prompt 定位人格，接受 stage 标签的 user message，
输出 YAML 字典。

stage 类型：
- first_opinion：读 router 卡片，给首发观点
- rebuttal：读 peer 的输出，反驳一句
- adjust：被 peer 反驳后回应（stage 3 调整）

3 个子类区别仅在 prompt 文件路径。
"""

from __future__ import annotations

import os
import re
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

PROVIDER = os.getenv("LLM_PROVIDER", "minimax").lower()

if PROVIDER == "minimax":
    from openai import OpenAI
    if not os.getenv("MINIMAX_API_KEY"):
        print("❌ 请在 .env 设置 MINIMAX_API_KEY")
        sys.exit(1)
    _client = OpenAI(
        api_key=os.getenv("MINIMAX_API_KEY"),
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
    )
    _model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
elif PROVIDER == "anthropic":
    from anthropic import Anthropic
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ 请在 .env 设置 ANTHROPIC_API_KEY")
        sys.exit(1)
    _client = Anthropic()
    _model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")
else:
    raise ValueError(f"未知 LLM_PROVIDER: {PROVIDER}")


def _strip_reasoning_and_codeblock(raw: str) -> str:
    """剥离 <think>...</think> 标签 + ```yaml ``` 代码块标记。"""
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```ya?ml\s*\n?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()
    return cleaned


def _call_llm(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    """统一 LLM 调用接口（MiniMax / Anthropic 双适配）。
    自动剥离推理模型的 <think>...</think> 段——所有下游消费者拿到的都是干净文本。
    """
    if PROVIDER == "minimax":
        resp = _client.chat.completions.create(
            model=_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        raw = resp.choices[0].message.content or ""
    else:
        resp = _client.messages.create(
            model=_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = resp.content[0].text

    # 统一剥离 reasoning model 的 <think>...</think> 段
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def _parse_yaml_with_retry(raw: str) -> dict | None:
    """解析 YAML。失败返回 None。"""
    cleaned = _strip_reasoning_and_codeblock(raw)
    try:
        parsed = yaml.safe_load(cleaned) if cleaned else None
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


# ============= Base Agent =============

class BaseAgent:
    """3 个 persona agent 的共用基类。子类只需配置 persona + prompt 文件。"""

    def __init__(self, persona: str, prompt_file: str):
        self.persona = persona
        self.system_prompt = (HERE / "prompts" / prompt_file).read_text(encoding="utf-8")

    def _invoke(self, user_message: str, max_retries: int = 1) -> dict:
        """调 LLM + 解析 YAML，失败重试 max_retries 次。"""
        last_raw = ""
        for attempt in range(max_retries + 1):
            raw = _call_llm(self.system_prompt, user_message)
            last_raw = raw
            parsed = _parse_yaml_with_retry(raw)
            if parsed is not None:
                return parsed
        return {
            "agent": self.persona,
            "stage": "ERROR",
            "error": "yaml_parse_failed",
            "raw_text": last_raw[:500],
        }

    # ---------- Stage 1 ----------
    def first_opinion(self, router_card: dict) -> dict:
        card_yaml = yaml.dump(router_card, allow_unicode=True, sort_keys=False)
        msg = (
            "<<<STAGE: first_opinion>>>\n\n"
            f"<<<ROUTER_CARD>>>\n{card_yaml}<<<END>>>\n"
        )
        return self._invoke(msg)

    # ---------- Stage 2 ----------
    def rebuttal(
        self,
        router_card: dict,
        target: str,
        peer_first: dict,
        round_num: int = 1,
        peer_adjust_round1: dict | None = None,
    ) -> dict:
        card_yaml = yaml.dump(router_card, allow_unicode=True, sort_keys=False)
        peer_first_yaml = yaml.dump(peer_first, allow_unicode=True, sort_keys=False)

        parts = [
            f"<<<STAGE: rebuttal>>>",
            f"<<<ROUND: {round_num}>>>",
            f"<<<TARGET_PEER: {target}>>>",
            f"<<<ROUTER_CARD>>>\n{card_yaml}<<<END>>>",
            f"<<<PEER_FIRST_OPINION>>>\n{peer_first_yaml}<<<END>>>",
        ]

        if round_num == 2 and peer_adjust_round1:
            adj_yaml = yaml.dump(peer_adjust_round1, allow_unicode=True, sort_keys=False)
            parts.append(f"<<<PEER_ADJUST_ROUND_1>>>\n{adj_yaml}<<<END>>>")

        return self._invoke("\n\n".join(parts))

    # ---------- Stage 3 ----------
    def adjust(
        self,
        router_card: dict,
        my_first: dict,
        trigger: dict,
        round_num: int = 1,
        triggered_by: str = "peer_rebuttal",
    ) -> dict:
        card_yaml = yaml.dump(router_card, allow_unicode=True, sort_keys=False)
        my_first_yaml = yaml.dump(my_first, allow_unicode=True, sort_keys=False)
        trigger_yaml = yaml.dump(trigger, allow_unicode=True, sort_keys=False)

        msg = "\n\n".join([
            f"<<<STAGE: adjust>>>",
            f"<<<ROUND: {round_num}>>>",
            f"<<<TRIGGERED_BY: {triggered_by}>>>",
            f"<<<ROUTER_CARD>>>\n{card_yaml}<<<END>>>",
            f"<<<MY_FIRST_OPINION>>>\n{my_first_yaml}<<<END>>>",
            f"<<<TRIGGER>>>\n{trigger_yaml}<<<END>>>",
        ])
        return self._invoke(msg)


# ============= 3 个 persona =============

class ZengGuoFan(BaseAgent):
    def __init__(self):
        super().__init__("曾国藩", "zengguofan_v0.1.txt")


class SuShi(BaseAgent):
    def __init__(self):
        super().__init__("苏轼", "sushi_v0.1.txt")


class WangYangMing(BaseAgent):
    def __init__(self):
        super().__init__("王阳明", "wangyangming_v0.1.txt")


PERSONAS = {
    "曾国藩": ZengGuoFan(),
    "苏轼": SuShi(),
    "王阳明": WangYangMing(),
}


if __name__ == "__main__":
    print(f"[agents] LLM_PROVIDER={PROVIDER}, model={_model}")
    print(f"[agents] PERSONAS loaded: {list(PERSONAS.keys())}")

    sample_card = {
        "crisis": False,
        "category": "跳槽 / 求职 / offer 选择",
        "fact_reconstruction": {
            "objective": "30 岁产品经理，月薪 25k，创业 offer 40k+期权，老婆怀孕，一周内决定。",
            "stakeholders": ["老婆"],
        },
        "core": {"intent": "decision", "user_already_knows": False},
        "emotional_keywords": ["焦虑", "睡不好"],
        "score": 75,
    }

    print("\n[smoke test] 曾国藩 first_opinion ...")
    out = PERSONAS["曾国藩"].first_opinion(sample_card)
    print(yaml.dump(out, allow_unicode=True, sort_keys=False, indent=2))
