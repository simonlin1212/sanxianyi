"""
M0.5 5 困境实测

跑 5 个代表性用例覆盖所有分支：
- id 5 危机边缘 → crisis_response
- id 6 超短输入  → followup_question
- id 7 纯倾诉    → listen 模式
- id 8 双重困境  → 2 轮辩论 + handover
- id 4 35 岁焦虑 → 2 轮辩论 advice

输出：outputs/m05_test_report.md + 每用例 outputs/run_*_m05_case_<id>.md
"""

from __future__ import annotations

import time
import yaml
from pathlib import Path
from datetime import datetime

from orchestrator import run

HERE = Path(__file__).parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

SELECTED_IDS = [5, 6, 7, 8, 4]


def main():
    with open(HERE / "test_cases.yaml", encoding="utf-8") as f:
        all_cases = yaml.safe_load(f)["test_cases"]

    cases = [c for c in all_cases if c.get("id") in SELECTED_IDS and c.get("input")]
    if len(cases) != len(SELECTED_IDS):
        print(f"⚠️  期望 {len(SELECTED_IDS)} 个用例，实际找到 {len(cases)}")

    report_lines = [
        "# M0.5 5 困境实测报告\n",
        f"- 时间：{datetime.now().isoformat()}",
        f"- 用例：{SELECTED_IDS}\n",
    ]

    summary_table = ["| ID | 名称 | output_type | 耗时 | agents | flagged |", "|---|---|---|---|---|---|"]

    for case in cases:
        cid = case["id"]
        name = case["name"]
        print(f"\n{'='*60}")
        print(f"[用例 {cid}] {name}")
        print(f"{'='*60}")

        t0 = time.time()
        try:
            result = run(case["input"], save_md=True, save_label=f"m05_case_{cid}")
            elapsed = result["elapsed_seconds"]
            otype = result["output_type"]
            agents = result.get("agents_consulted", [])
            flagged = len(result.get("debug", {}).get("fabricated_quotes_flagged", []))

            print(f"  ✅ 完成 {elapsed}s | {otype} | agents={agents} | flagged={flagged}")
            summary_table.append(
                f"| {cid} | {name} | {otype} | {elapsed}s | {','.join(agents) or '—'} | {flagged} |"
            )

            report_lines.append(f"\n---\n## 用例 {cid}：{name}\n")
            report_lines.append(f"**输入**：\n```\n{case['input'].strip()}\n```\n")
            report_lines.append(f"**结果**：")
            report_lines.append(f"- output_type: `{otype}`")
            report_lines.append(f"- 耗时: {elapsed}s")
            report_lines.append(f"- agents_consulted: {agents}")
            report_lines.append(f"- 编造引文 flagged: {flagged}")
            if flagged:
                fl = result["debug"]["fabricated_quotes_flagged"]
                report_lines.append("  - 详情：")
                for f in fl:
                    report_lines.append(
                        f"    - {f['persona']}: '{f['quote']}' "
                        f"（声称出处: {f['claimed_source']}）"
                    )
            report_lines.append(f"\n**主持人输出**：\n\n{result['text']}\n")

        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            print(f"  ❌ 异常 {elapsed}s: {e}")
            summary_table.append(f"| {cid} | {name} | ERROR | {elapsed}s | — | — |")
            report_lines.append(f"\n---\n## 用例 {cid}：{name}\n\n❌ 异常: `{e}`\n")

    report_lines.insert(3, "\n## 汇总\n")
    report_lines.insert(4, "\n".join(summary_table))
    report_lines.insert(5, "")

    out_path = OUT / "m05_test_report.md"
    out_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n📄 报告：{out_path}")


if __name__ == "__main__":
    main()
