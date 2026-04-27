"""
M0.4 Router 入口

复用 router_test.py 已验证的 prompt（prompts/router_v0.2.txt）+ agents.py 的 LLM 调用。
"""

from __future__ import annotations

from pathlib import Path
from agents import _call_llm, _parse_yaml_with_retry

HERE = Path(__file__).parent
ROUTER_PROMPT = (HERE / "prompts" / "router_v0.2.txt").read_text(encoding="utf-8")


def route(user_input: str) -> dict:
    """调 Router 输出困境卡片。失败返回兜底卡片让 moderator 走追问分支。"""
    raw = _call_llm(ROUTER_PROMPT, user_input, max_tokens=8192)
    parsed = _parse_yaml_with_retry(raw)
    if parsed is None:
        return {
            "crisis": False,
            "score": 0,
            "needs_followup": True,
            "followup_questions": ["能再说说你现在最困扰的是什么吗？"],
            "_error": "router_yaml_parse_failed",
            "_raw": raw[:500],
        }
    return parsed


if __name__ == "__main__":
    sample = (
        "30 岁，互联网产品经理，现在月薪 25k，最近收到一家创业公司 offer，"
        "给我 40k + 期权。但我老婆怀孕了，希望我稳定。我感觉大厂明年要裁员，"
        "又怕创业公司一年就倒。一周内必须答复，已经睡不好两个礼拜了。"
    )
    import yaml
    card = route(sample)
    print(yaml.dump(card, allow_unicode=True, sort_keys=False))
