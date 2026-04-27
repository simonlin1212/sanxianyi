"""
M0.4 编排入口

CLI 用法：
    python3 orchestrator.py "我 30 岁，想跳槽，老婆怀孕..."

Python 用法：
    from orchestrator import run
    result = run(user_input)
    print(result["text"])
"""

from __future__ import annotations

import sys
import time
import yaml
from pathlib import Path
from datetime import datetime

from moderator import Moderator

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def run(user_input: str, save_md: bool = False, save_label: str = "manual") -> dict:
    """
    跑一次完整 pipeline：Router → 主持人调度 → 综合输出。

    返回 dict 含：
      - output_type: crisis_response / followup_question / full_response
      - text: 给用户的 markdown
      - agents_consulted: 实际发言的 persona 列表
      - debug: 完整调试信息（router_card / opinions / round_1 / round_2 / flagged）
      - elapsed_seconds: 耗时
    """
    t0 = time.time()
    moderator = Moderator()
    result = moderator.handle(user_input)
    result["elapsed_seconds"] = round(time.time() - t0, 1)

    if save_md:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"run_{ts}_{save_label}.md"
        debug_path = OUTPUT_DIR / f"run_{ts}_{save_label}.debug.yaml"

        md_lines = [
            f"# 智囊团回复\n",
            f"- 时间：{datetime.now().isoformat()}",
            f"- 耗时：{result['elapsed_seconds']}s",
            f"- 类型：{result['output_type']}",
            f"- 参与 agent：{result['agents_consulted']}\n",
            "---\n",
            "## 用户输入\n",
            f"```\n{user_input.strip()}\n```\n",
            "---\n",
            "## 主持人输出\n",
            result["text"],
        ]
        out_path.write_text("\n".join(md_lines), encoding="utf-8")

        debug_yaml = yaml.dump(result.get("debug", {}), allow_unicode=True, sort_keys=False)
        debug_path.write_text(debug_yaml, encoding="utf-8")

        print(f"[orchestrator] 输出 → {out_path}")
        print(f"[orchestrator] debug → {debug_path}")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 orchestrator.py \"<user_input>\"")
        print("\n或测试默认困境：")
        user_in = (
            "30 岁，互联网产品经理，现在月薪 25k，最近收到一家创业公司 offer，"
            "给我 40k + 期权。但我老婆怀孕了，希望我稳定。我感觉大厂明年要裁员，"
            "又怕创业公司一年就倒。一周内必须答复，已经睡不好两个礼拜了。"
        )
        print(f"\n[默认困境]\n{user_in}\n")
    else:
        user_in = sys.argv[1]

    result = run(user_in, save_md=True, save_label="cli")
    print("\n" + "=" * 60)
    print(result["text"])
    print("=" * 60)
    print(f"\n耗时 {result['elapsed_seconds']}s | 类型 {result['output_type']}")
