"""Run benchmark: read annotated CSV, compute 4 metrics, save results."""

import csv
import json
import sys
from pathlib import Path

# ---------- config ----------
CSV_PATH = Path(__file__).resolve().parent / "benchmark_annotation_template.csv"
OUTPUT_DIR = Path(__file__).resolve().parent
# ----------------------------

def main():
    if not CSV_PATH.exists():
        print(f"[ERROR] File not found: {CSV_PATH}")
        sys.exit(1)

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_raw = len(rows)
    print(f"\n  Loaded {total_raw} rows from {CSV_PATH.name}")

    # ---------- filter valid ----------
    data = [r for r in rows if r.get("valid", "").strip().lower() == "true"]
    discarded = total_raw - len(data)

    # ---------- compute hit ----------
    for r in data:
        score = float(r.get("system_score", 0))
        sys_label = "safe" if score < 30 else "risk"
        true_label = r.get("true_label", "").strip().lower()
        r["_hit"] = (
            1
            if (true_label == "real" and sys_label == "safe")
            or (true_label == "fake" and sys_label == "risk")
            else 0
        )
        r["_sys_label"] = sys_label

    total = len(data)
    correct = sum(r["_hit"] for r in data)

    # ---------- 4 metrics ----------
    accuracy = correct / total * 100

    fake_total = sum(1 for r in data if r["true_label"] == "fake")
    fake_caught = sum(1 for r in data if r["true_label"] == "fake" and r["_hit"])
    fake_recall = fake_caught / fake_total * 100 if fake_total > 0 else 0

    real_total = sum(1 for r in data if r["true_label"] == "real")
    real_falsed = sum(1 for r in data if r["true_label"] == "real" and not r["_hit"])
    false_alarm = real_falsed / real_total * 100 if real_total > 0 else 0

    real_scores = [float(r["system_score"]) for r in data if r["true_label"] == "real"]
    fake_scores = [float(r["system_score"]) for r in data if r["true_label"] == "fake"]
    real_avg = sum(real_scores) / len(real_scores) if real_scores else 0
    fake_avg = sum(fake_scores) / len(fake_scores) if fake_scores else 0
    risk_gap = fake_avg - real_avg

    # ---------- print table ----------
    print()
    print("=" * 72)
    print("  Benchmark Results: Multi-Agent Lie Detection System")
    print("=" * 72)
    print("  Total samples: {}  (real={}, fake={})".format(total, real_total, fake_total))
    if discarded:
        print("  (discarded {} invalid samples)".format(discarded))
    print()
    h = "  {:<30} {:>8} {:>12} {:>12}  {:>7} {:>7}".format(
        "Method", "Accuracy", "Fake Recall", "False Alarm", "Fake_avg", "Real_avg"
    )
    s = "  {:<30} {:>8} {:>12} {:>12}  {:>7} {:>7}".format(
        "-" * 30, "-" * 8, "-" * 12, "-" * 12, "-" * 7, "-" * 7
    )
    r = "  {:<30} {:>7.1f}% {:>11.1f}% {:>11.1f}%  {:>6.1f} {:>6.1f}".format(
        "Your Multi-Agent System", accuracy, fake_recall, false_alarm, fake_avg, real_avg
    )
    print(h)
    print(s)
    print(r)
    print()
    print("  Avg Risk Gap (fake - real): {:.1f}".format(risk_gap))
    print("=" * 72)

    # ---------- save results ----------
    results = {
        "total_raw": total_raw,
        "discarded": discarded,
        "total_valid": total,
        "real_count": real_total,
        "fake_count": fake_total,
        "accuracy_pct": round(accuracy, 1),
        "fake_recall_pct": round(fake_recall, 1),
        "false_alarm_pct": round(false_alarm, 1),
        "real_avg_score": round(real_avg, 1),
        "fake_avg_score": round(fake_avg, 1),
        "risk_gap": round(risk_gap, 1),
    }

    # JSON
    json_path = OUTPUT_DIR / "benchmark_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("  Saved: {}".format(json_path.name))

    # CSV results table
    csv_res_path = OUTPUT_DIR / "benchmark_results_table.csv"
    with open(csv_res_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Method", "Accuracy", "Fake Recall", "False Alarm", "Fake_avg", "Real_avg"])
        w.writerow([
            "Your Multi-Agent System",
            "{:.1f}%".format(accuracy),
            "{:.1f}%".format(fake_recall),
            "{:.1f}%".format(false_alarm),
            "{:.1f}".format(fake_avg),
            "{:.1f}".format(real_avg),
        ])
    print("  Saved: {}".format(csv_res_path.name))

    # Detail CSV
    detail_path = OUTPUT_DIR / "benchmark_detail_output.csv"
    detail_fields = [
        "filename", "claimed_job", "true_label", "valid",
        "system_score", "system_label", "system_reason", "hit", "note",
    ]
    with open(detail_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=detail_fields)
        writer.writeheader()
        for r in data:
            writer.writerow({
                "filename": r["filename"],
                "claimed_job": r.get("claimed_job", ""),
                "true_label": r["true_label"],
                "valid": "true",
                "system_score": r["system_score"],
                "system_label": r["_sys_label"],
                "system_reason": r.get("system_reason", ""),
                "hit": "\u2714" if r["_hit"] else "\u2718",
                "note": r.get("note", ""),
            })
    print("  Saved: {}".format(detail_path.name))
    print()


if __name__ == "__main__":
    main()