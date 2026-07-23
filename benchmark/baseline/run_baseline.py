"""Baseline: use a single LLM call (pure dialogue) to judge real vs fake.
   V2: outputs continuous score (0-100), label is derived from score.
"""

import csv
import json
import sys
import time
from pathlib import Path

# ---------- paths ----------
BASE_DIR = Path(__file__).resolve().parent.parent  # benchmark/
ANNOTATED_CSV = BASE_DIR / "benchmark_annotation_template.csv"
RAW_JSON = BASE_DIR / "supabase_raw_export.json"
BASELINE_DIR = Path(__file__).resolve().parent
BASELINE_RESULTS = BASELINE_DIR / "baseline_results.json"
BASELINE_CSV = BASELINE_DIR / "baseline_results.csv"
# ----------------------------

BASELINE_PROMPT = """你是一个职业身份真实性评估助手。

【任务】
给你一段多轮对话，对话中有一个用户自称某种职业身份。请判断这个用户的职业身份是否可信。

【输出要求】
只输出两行：
reason: 一句话理由（20字以内）
score: 0-100的虚假风险分数，0=完全可信，100=肯定虚假

评分参考：
- 0-30: 可信
- 31-50: 中等风险
- 51-70: 较高风险
- 71-100: 虚假

基于对话中的具体细节、专业性、一致性和真实性来判断。

【对话】
{dialogue}

【输出】"""


def extract_pure_dialogue(filename, records):
    """Extract only user and AI messages (no thinking/analysis) for a given filename."""
    for rec in records:
        cj = rec.get("content_json")
        if not cj or not isinstance(cj, dict):
            continue
        if rec["filename"] != filename:
            continue
        rd = cj.get("round_records", [])
        lines = []
        for r_item in rd:
            ui = r_item.get("user_input", "").strip()
            af = r_item.get("ai_followup", "").strip()
            if ui:
                lines.append("用户: " + ui)
            if af:
                lines.append("AI: " + af)
        return "\n".join(lines)
    return ""


def parse_llm_response(text):
    """Parse 'reason: ...' and 'score: ...' from LLM output.
    label is derived from score: score >= 50 -> fake, else real.
    """
    reason = ""
    score = 50.0  # fallback
    for line in text.strip().split("\n"):
        s = line.strip().lower()
        if s.startswith("reason:"):
            reason = line.replace("reason:", "", 1).strip()
        elif s.startswith("score:"):
            try:
                score = float(s.replace("score:", "").strip())
                score = max(0.0, min(100.0, score))
            except ValueError:
                score = 50.0
    label = "fake" if score >= 50 else "real"
    return label, reason, score


def main():
    with open(RAW_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)
    print("[OK] Loaded {} raw records".format(len(records)))

    with open(ANNOTATED_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    samples = [r for r in all_rows if r.get("valid", "").strip().lower() == "true"]
    print("[OK] {} valid samples to evaluate".format(len(samples)))

    sys.path.insert(0, str(BASE_DIR.parent))
    from llm_client import get_llm
    llm = get_llm(temperature=0.1)

    results = []
    for i, row in enumerate(samples):
        filename = row["filename"]
        dialogue = extract_pure_dialogue(filename, records)

        if not dialogue:
            print("  [SKIP] {}: no dialogue found".format(filename))
            continue

        prompt = BASELINE_PROMPT.format(dialogue=dialogue)

        print("  [{}/{}] {}...".format(i + 1, len(samples), filename), end=" ", flush=True)

        try:
            resp = llm.invoke(prompt)
            raw = resp.content.strip()
            label, reason, baseline_score = parse_llm_response(raw)
            print("-> {} (score={})".format(label, baseline_score))
        except Exception as e:
            print("-> ERROR: {}".format(e))
            label, reason, baseline_score = "", "", None

        true_label = row.get("true_label", "").strip().lower()
        system_score = float(row.get("system_score", 0))
        system_label = "safe" if system_score < 25 else "risk"

        results.append({
            "filename": filename,
            "claimed_job": row.get("claimed_job", ""),
            "true_label": true_label,
            "baseline_label": label,
            "baseline_score": baseline_score,
            "baseline_reason": reason[:100] if reason else "",
            "system_score": system_score,
            "system_label": system_label,
        })

        time.sleep(0.5)

    with open(BASELINE_RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n[OK] Saved raw results: {}".format(BASELINE_RESULTS.name))

    total = len(results)
    valid = [r for r in results if r["baseline_label"] in ("real", "fake") and r["true_label"] in ("real", "fake")]
    print("\n  Valid LLM responses: {}/{}".format(len(valid), total))

    if not valid:
        print("[ERROR] No valid baseline results to compute metrics.")
        return

    real_scores_ma = [r["system_score"] for r in valid if r["true_label"] == "real"]
    fake_scores_ma = [r["system_score"] for r in valid if r["true_label"] == "fake"]
    real_avg_ma = sum(real_scores_ma) / len(real_scores_ma) if real_scores_ma else 0
    fake_avg_ma = sum(fake_scores_ma) / len(fake_scores_ma) if fake_scores_ma else 0
    risk_gap_ma = fake_avg_ma - real_avg_ma

    baseline_correct = sum(1 for r in valid if r["baseline_label"] == r["true_label"])
    baseline_acc = baseline_correct / len(valid) * 100

    baseline_fake_total = sum(1 for r in valid if r["true_label"] == "fake")
    baseline_fake_caught = sum(1 for r in valid if r["baseline_label"] == "fake" and r["true_label"] == "fake")
    baseline_fake_recall = baseline_fake_caught / baseline_fake_total * 100 if baseline_fake_total > 0 else 0

    baseline_real_total = sum(1 for r in valid if r["true_label"] == "real")
    baseline_real_falsed = sum(1 for r in valid if r["baseline_label"] == "fake" and r["true_label"] == "real")
    baseline_false_alarm = baseline_real_falsed / baseline_real_total * 100 if baseline_real_total > 0 else 0

    baseline_real_scores = [r.get("baseline_score") or 0 for r in valid if r["true_label"] == "real"]
    baseline_fake_scores = [r.get("baseline_score") or 0 for r in valid if r["true_label"] == "fake"]
    baseline_real_avg = sum(baseline_real_scores) / len(baseline_real_scores) if baseline_real_scores else 0
    baseline_fake_avg = sum(baseline_fake_scores) / len(baseline_fake_scores) if baseline_fake_scores else 0
    baseline_risk_gap = baseline_fake_avg - baseline_real_avg

    sys_correct = sum(1 for r in valid if (r["true_label"] == "real" and r["system_label"] == "safe") or (r["true_label"] == "fake" and r["system_label"] == "risk"))
    sys_acc = sys_correct / len(valid) * 100
    sys_fake_caught = sum(1 for r in valid if r["true_label"] == "fake" and r["system_label"] == "risk")
    sys_fake_recall = sys_fake_caught / baseline_fake_total * 100 if baseline_fake_total > 0 else 0
    sys_real_falsed = sum(1 for r in valid if r["true_label"] == "real" and r["system_label"] == "risk")
    sys_false_alarm = sys_real_falsed / baseline_real_total * 100 if baseline_real_total > 0 else 0

    print()
    print("=" * 90)
    print("  Benchmark Comparison: Baseline vs v3 Multi-Agent System")
    print("=" * 90)
    print("  Total samples: {}  (real={}, fake={})".format(len(valid), baseline_real_total, baseline_fake_total))
    print("  Baseline label derived from score: score >= 50 -> fake, score < 50 -> real")
    print()
    h = "  {:<28} {:>8} {:>10} {:>10} {:>8} {:>8} {:>8}".format(
        "Method", "Accuracy", "Fk Recall", "F. Alarm", "R_avg", "F_avg", "Risk Gap"
    )
    s = "  {:<28} {:>8} {:>10} {:>10} {:>8} {:>8} {:>8}".format(
        "-" * 28, "-" * 8, "-" * 10, "-" * 10, "-" * 8, "-" * 8, "-" * 8,
    )
    r1 = "  {:<28} {:>7.1f}% {:>9.1f}% {:>9.1f}% {:>7.1f} {:>7.1f} {:>7.1f}".format(
        "Baseline (Single LLM)",
        baseline_acc, baseline_fake_recall, baseline_false_alarm,
        baseline_real_avg, baseline_fake_avg, baseline_risk_gap,
    )
    r2 = "  {:<28} {:>7.1f}% {:>9.1f}% {:>9.1f}% {:>7.1f} {:>7.1f} {:>7.1f}".format(
        "v3 Multi-Agent System",
        sys_acc, sys_fake_recall, sys_false_alarm,
        real_avg_ma, fake_avg_ma, risk_gap_ma,
    )
    print(h)
    print(s)
    print(r1)
    print(r2)
    print("=" * 90)

    comp_path = BASELINE_DIR / "benchmark_comparison.csv"
    with open(comp_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Method", "Accuracy", "Fake Recall", "False Alarm", "Real_avg", "Fake_avg", "Risk Gap"])
        w.writerow(["Baseline (Single LLM)",
                     "{:.1f}%".format(baseline_acc),
                     "{:.1f}%".format(baseline_fake_recall),
                     "{:.1f}%".format(baseline_false_alarm),
                     "{:.1f}".format(baseline_real_avg),
                     "{:.1f}".format(baseline_fake_avg),
                     "{:.1f}".format(baseline_risk_gap)])
        w.writerow(["v3 Multi-Agent System",
                     "{:.1f}%".format(sys_acc),
                     "{:.1f}%".format(sys_fake_recall),
                     "{:.1f}%".format(sys_false_alarm),
                     "{:.1f}".format(real_avg_ma),
                     "{:.1f}".format(fake_avg_ma),
                     "{:.1f}".format(risk_gap_ma)])
    print("  Saved: {}".format(comp_path.name))

    detail_fields = ["filename", "claimed_job", "true_label",
                     "baseline_label", "baseline_score", "baseline_reason",
                     "system_score", "system_label"]
    with open(BASELINE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=detail_fields)
        w.writeheader()
        for r in valid:
            w.writerow({
                "filename": r["filename"],
                "claimed_job": r.get("claimed_job", ""),
                "true_label": r["true_label"],
                "baseline_label": r["baseline_label"],
                "baseline_score": r.get("baseline_score", ""),
                "baseline_reason": r.get("baseline_reason", ""),
                "system_score": r["system_score"],
                "system_label": r["system_label"],
            })
    print("  Saved: {}".format(BASELINE_CSV.name))
    print()


if __name__ == "__main__":
    main()
