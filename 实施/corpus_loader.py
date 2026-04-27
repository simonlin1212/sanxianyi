"""
M0.4 语料加载器 + 引文核验

职责：
- 加载 M0.2.5 三份语料 yaml 到内存
- 给主持人提供 verify_quote() 用于"引文打假"——检查 agent 输出引用的语录
  是否真的在语料库里（防止 LLM 编造）
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import yaml
import re

CORPUS_DIR = Path(__file__).parent.parent / "设计文档"

PERSONA_FILES = {
    "曾国藩": "M0.2-曾国藩-语料.yaml",
    "苏轼":   "M0.2-苏轼-语料.yaml",
    "王阳明": "M0.2-王阳明-语料.yaml",
}


@lru_cache(maxsize=3)
def load_persona_corpus(persona: str) -> dict:
    """加载某 persona 的完整语料 yaml。结果缓存，避免重复磁盘读。"""
    if persona not in PERSONA_FILES:
        raise ValueError(f"未知 persona: {persona}（应为 {list(PERSONA_FILES)}）")
    path = CORPUS_DIR / PERSONA_FILES[persona]
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def all_quotes(persona: str) -> list[dict]:
    """返回某 persona 全部引文的扁平列表，每条含 text/source/confidence/scenes。"""
    data = load_persona_corpus(persona)
    flat = []
    for theme in data.get("themes", []):
        for q in theme.get("quotes", []):
            flat.append({
                "id": q.get("id"),
                "text": q.get("text", ""),
                "source": q.get("source", ""),
                "confidence": q.get("confidence", "LOW"),
                "theme": theme.get("name", ""),
                "scenes": q.get("scenes", []),
            })
    return flat


def _normalize(text: str) -> str:
    """归一化文本：去标点空白，方便子串匹配。"""
    return re.sub(r"[\s　，。、；：！？""''「」《》\(\)（）\.\,\;\:\!\?\"\']", "", text or "")


def verify_quote(persona: str, agent_quoted_text: str) -> tuple[bool, dict | None]:
    """
    检查 agent 输出里引用的 text 是否在该 persona 的语料库里。

    返回 (is_real, matched_entry):
      - is_real=True 时 matched_entry 是命中的语料条目
      - is_real=False 时 matched_entry=None

    匹配策略：归一化后子串匹配（正向或反向，agent 可能引完整词或半句）。
    """
    if not agent_quoted_text or not agent_quoted_text.strip():
        return False, None

    needle = _normalize(agent_quoted_text)
    if not needle or len(needle) < 3:
        return False, None

    for entry in all_quotes(persona):
        haystack = _normalize(entry["text"])
        if not haystack:
            continue
        if needle in haystack or haystack in needle:
            return True, entry

    return False, None


def get_quotes_by_scene(persona: str, scene_keyword: str, top_k: int = 5) -> list[dict]:
    """
    按场景标签检索引文。

    返回最多 top_k 条，confidence=HIGH 优先。
    """
    matches = []
    for entry in all_quotes(persona):
        if any(scene_keyword in str(s) for s in entry.get("scenes", [])):
            matches.append(entry)
    matches.sort(key=lambda x: 0 if x["confidence"] == "HIGH" else (1 if x["confidence"] == "MED" else 2))
    return matches[:top_k]


# ============= 自检 =============

def _self_check():
    """启动时自检：3 份 yaml 都能加载，且每份都 ≥ 40 条 HIGH+MED。"""
    for persona in PERSONA_FILES:
        quotes = all_quotes(persona)
        high_med = sum(1 for q in quotes if q["confidence"] in ("HIGH", "MED"))
        print(f"[corpus] {persona}: {len(quotes)} 条 ({high_med} HIGH+MED)")
        assert high_med >= 40, f"{persona} 高质量条数不够: {high_med}"


if __name__ == "__main__":
    _self_check()

    test_cases = [
        ("曾国藩", "些小得失不足患"),
        ("苏轼", "莫听穿林打叶声"),
        ("苏轼", "莫笑农家腊酒浑"),
        ("王阳明", "心即理"),
        ("王阳明", "你应该多读书"),
    ]

    print("\n[verify_quote 测试]")
    for persona, text in test_cases:
        ok, entry = verify_quote(persona, text)
        marker = "✅" if ok else "❌"
        src = entry["source"] if entry else "—"
        print(f"  {marker} {persona}: '{text}' → {src}")
