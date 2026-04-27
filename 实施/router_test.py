#!/usr/bin/env python3
"""
M0.1 Router 测试脚本
读 prompts/router_v0.2.txt → 跑 test_cases.yaml → 输出 outputs/router_test_report.md
"""

import os
import re
import sys
import yaml
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic

HERE = Path(__file__).parent

# ============= 环境检查 =============

load_dotenv(HERE / ".env")

PROVIDER = os.getenv("LLM_PROVIDER", "minimax").lower()  # minimax / anthropic

if PROVIDER == "minimax":
    from openai import OpenAI
    if not os.getenv("MINIMAX_API_KEY"):
        print("❌ 请在 .env 里设置 MINIMAX_API_KEY")
        print("   去 https://platform.minimaxi.com/ 申请")
        sys.exit(1)
    client = OpenAI(
        api_key=os.getenv("MINIMAX_API_KEY"),
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
    )
    MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
elif PROVIDER == "anthropic":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ 请在 .env 里设置 ANTHROPIC_API_KEY")
        print("   去 https://console.anthropic.com/ 申请")
        sys.exit(1)
    client = Anthropic()
    MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")
else:
    print(f"❌ 不支持的 LLM_PROVIDER: {PROVIDER}（应为 minimax / anthropic）")
    sys.exit(1)

SYSTEM_PROMPT = (HERE / "prompts" / "router_v0.2.txt").read_text(encoding="utf-8")

with open(HERE / "test_cases.yaml", encoding="utf-8") as f:
    TEST_CASES = yaml.safe_load(f)["test_cases"]

# ============= 桶号关键词映射（用于断言）=============

BUCKET_KEYWORDS = {
    1: ["跳槽", "求职", "offer", "面试", "新工作"],
    2: ["领导", "同事", "PUA", "冲突", "甩锅", "站队", "关系"],
    3: ["薪资", "晋升", "绩效", "加薪", "调薪"],
    4: ["离职", "裁员", "劝退", "N+1"],
    5: ["35", "中年", "转行", "长期", "方向", "迷茫"],
    6: ["创业", "副业", "自由职业", "合伙"],
    7: ["压力", "倦怠", "burnout", "996", "意义", "不想上班"],
    8: ["家庭", "孩子", "老婆", "老公", "父母", "回家", "留城"],
}


def check_bucket(category_str, bucket_num):
    if not category_str or category_str == "null":
        return False
    cs = str(category_str).lower()
    return any(kw.lower() in cs for kw in BUCKET_KEYWORDS.get(bucket_num, []))


# ============= 跑单个测试 =============

def run_test(case):
    """调 API → 返回 (raw_text, parsed_yaml | None)"""
    if PROVIDER == "minimax":
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": case["input"]},
            ],
        )
        raw = response.choices[0].message.content or ""
    else:  # anthropic
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": case["input"]}],
        )
        raw = response.content[0].text

    # 剥离 reasoning model 的 <think>...</think> 标签（MiniMax-M2 / DeepSeek-R1 等）
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # 剥离 ```yaml ... ``` 代码块标记（如果模型添加）
    cleaned = re.sub(r"^```ya?ml\s*\n?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()

    try:
        parsed = yaml.safe_load(cleaned) if cleaned else None
        if not isinstance(parsed, dict):
            parsed = None
    except Exception:
        parsed = None
    return cleaned, parsed


# ============= 断言（基础 + 边缘用例）=============

def assert_case(case, parsed):
    expected = case.get("expected", {})
    results = []

    if parsed is None:
        results.append(("YAML 格式", False, "yaml.safe_load 解析失败"))
        return results

    if "crisis" in expected:
        actual = parsed.get("crisis")
        results.append(("crisis", actual == expected["crisis"],
                        f"expected={expected['crisis']}, got={actual}"))

    if "category_bucket" in expected:
        actual_cat = parsed.get("category") or ""
        ok = check_bucket(actual_cat, expected["category_bucket"])
        results.append(("category_bucket", ok,
                        f"expected bucket={expected['category_bucket']}, got='{actual_cat}'"))

    if "category_bucket_in" in expected:
        actual_cat = parsed.get("category") or ""
        ok = any(check_bucket(actual_cat, b) for b in expected["category_bucket_in"])
        results.append(("category_bucket_in", ok,
                        f"expected one of {expected['category_bucket_in']}, got='{actual_cat}'"))

    if "score_min" in expected:
        actual = parsed.get("score", 0) or 0
        results.append(("score_min", actual >= expected["score_min"],
                        f"expected >= {expected['score_min']}, got={actual}"))

    if "score_max" in expected:
        actual = parsed.get("score", 100) or 0
        results.append(("score_max", actual <= expected["score_max"],
                        f"expected <= {expected['score_max']}, got={actual}"))

    if "score_range" in expected:
        actual = parsed.get("score", 0) or 0
        lo, hi = expected["score_range"]
        results.append(("score_range", lo <= actual <= hi,
                        f"expected {lo}-{hi}, got={actual}"))

    if "needs_followup" in expected:
        actual = parsed.get("needs_followup")
        results.append(("needs_followup", actual == expected["needs_followup"],
                        f"expected={expected['needs_followup']}, got={actual}"))

    if "intent" in expected:
        actual = (parsed.get("core") or {}).get("intent")
        results.append(("intent", actual == expected["intent"],
                        f"expected={expected['intent']}, got={actual}"))

    if "stakeholders_contains" in expected:
        sh = (parsed.get("fact_reconstruction") or {}).get("stakeholders") or []
        ok = all(any(c in str(s) for s in sh) for c in expected["stakeholders_contains"])
        results.append(("stakeholders_contains", ok,
                        f"expected contains {expected['stakeholders_contains']}, got={sh}"))

    if "crisis_reason_contains" in expected:
        reason = parsed.get("crisis_reason") or ""
        ok = any(c in reason for c in expected["crisis_reason_contains"])
        results.append(("crisis_reason_contains", ok,
                        f"expected any of {expected['crisis_reason_contains']}, got='{reason}'"))

    if "followup_questions_min" in expected:
        fq = parsed.get("followup_questions") or []
        results.append(("followup_questions_min", len(fq) >= expected["followup_questions_min"],
                        f"expected >= {expected['followup_questions_min']}, got={len(fq)}"))

    return results


# ============= 反面行为检查 =============

def check_anti_patterns(all_results):
    anti = {}

    forbidden = ["建议你", "我建议", "你应该", "不如试试", "推荐你"]
    v11 = []
    for r in all_results:
        for p in forbidden:
            if p in r["raw"]:
                v11.append(f"用例 {r['case']['id']}: 含'{p}'")
    anti[11] = (len(v11) == 0, v11 if v11 else "无")

    anti[12] = (None, "需人工审：检查每个 fact_reconstruction.objective 是否保留用户原话片段")

    critical_cases = [r for r in all_results if r["case"].get("severity") == "critical"]
    misses = [r["case"]["id"] for r in critical_cases
              if not r["parsed"] or r["parsed"].get("crisis") is not True]
    anti[13] = (len(misses) == 0, f"漏判用例: {misses}" if misses else "全部命中")

    yaml_fails = [r["case"]["id"] for r in all_results if r["parsed"] is None]
    anti[14] = (len(yaml_fails) == 0,
                f"YAML 解析失败用例: {yaml_fails}" if yaml_fails else "全部合法")

    sensitive = ["请提供您的薪资", "您的婚姻状况", "您的学历", "请填写"]
    v15 = []
    for r in all_results:
        if r["parsed"]:
            fq = r["parsed"].get("followup_questions") or []
            for q in fq:
                for s in sensitive:
                    if s in str(q):
                        v15.append(f"用例 {r['case']['id']}: '{q}'")
    anti[15] = (len(v15) == 0, v15 if v15 else "无")

    return anti


# ============= 写报告 =============

def write_report(all_results, anti):
    out_path = HERE / "outputs" / "router_test_report.md"
    lines = []
    passed = sum(1 for r in all_results if all(a[1] for a in r["assertions"]))

    lines.append("# M0.1 Router 测试报告\n")
    lines.append(f"- 时间: {datetime.now().isoformat()}")
    lines.append(f"- 模型: `{MODEL}`")
    lines.append(f"- 实际跑用例: {len(all_results)}")
    lines.append(f"- 通过: **{passed}/{len(all_results)}**\n")

    lines.append("## 反面行为检查\n")
    label = {11: "不给建议", 12: "复述用原话", 13: "危机必中", 14: "YAML 合法", 15: "无敏感问"}
    for k in sorted(anti.keys()):
        ok, detail = anti[k]
        sym = "⚠️ 待人工审" if ok is None else ("✅" if ok else "❌")
        lines.append(f"- **{k} {label[k]}**: {sym} {detail}")
    lines.append("")

    lines.append("## 用例详情\n")
    for r in all_results:
        case = r["case"]
        all_pass = all(a[1] for a in r["assertions"])
        sym = "✅" if all_pass else "❌"
        lines.append(f"\n### {sym} 用例 [{case['id']}] {case['name']}\n")
        lines.append("**输入**:\n")
        lines.append("```")
        lines.append(case.get("input", "").strip())
        lines.append("```\n")
        lines.append("**断言**:\n")
        for name, ok, detail in r["assertions"]:
            lines.append(f"- {'✅' if ok else '❌'} `{name}`: {detail}")
        lines.append("\n**Router 输出**:\n")
        lines.append("```yaml")
        lines.append(r["raw"].strip())
        lines.append("```\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ============= 主流程 =============

def main():
    print(f"模型: {MODEL}")
    print(f"总用例: {len(TEST_CASES)}（含 {sum(1 for c in TEST_CASES if c['type']=='anti_pattern')} 个反面行为检查）")
    print()

    runnable = [c for c in TEST_CASES if c["type"] != "anti_pattern"]
    print(f"实际跑 {len(runnable)} 个用例：\n")

    all_results = []
    for case in runnable:
        print(f"[{case['id']:>2}] {case['name']} ... ", end="", flush=True)
        try:
            raw, parsed = run_test(case)
            assertions = assert_case(case, parsed)
            all_pass = all(a[1] for a in assertions)
            print("✅" if all_pass else "❌")
            all_results.append({
                "case": case,
                "raw": raw,
                "parsed": parsed,
                "assertions": assertions,
            })
        except Exception as e:
            print(f"❌ 异常: {e}")
            all_results.append({
                "case": case,
                "raw": "",
                "parsed": None,
                "assertions": [("EXCEPTION", False, str(e))],
            })

    print("\n反面行为检查...")
    anti = check_anti_patterns(all_results)
    for k, (ok, detail) in sorted(anti.items()):
        sym = "⚠️ " if ok is None else ("✅" if ok else "❌")
        print(f"  {sym} {k}: {detail}")

    out_path = write_report(all_results, anti)
    print(f"\n报告: {out_path}")


if __name__ == "__main__":
    main()
