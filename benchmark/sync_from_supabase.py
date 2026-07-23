"""Pull latest data from Supabase, merge with existing annotations, save new template."""

import csv
import json
import os
import sys
from pathlib import Path

# ---------- paths ----------
BASE_DIR = Path(__file__).resolve().parent
EXISTING_CSV = BASE_DIR / "benchmark_annotation_template.csv"
OUTPUT_CSV = BASE_DIR / "benchmark_annotation_template.csv"
RAW_EXPORT = BASE_DIR / "supabase_raw_export.json"
# ---------------------------

def extract_system_reason(report_text):
    if not report_text:
        return ""
    lines = report_text.split("\n")
    stability = ""
    in_overall = False
    for line in lines:
        s = line.strip()
        if "\u603b\u4f53\u7ed3\u679c" in s or (s.startswith("###") and "1." in s):
            in_overall = True
            continue
        if in_overall:
            if not s:
                continue
            if s.startswith("###") or ("2." in s and "\u5173\u952e\u4f9d\u636e" in s):
                break
            if "/100" in s:
                rest = s.split("/100")[1]
                rest = rest.strip("* \t\u2014\u2013-")
                if rest:
                    stability = rest
                continue
            stability = s.strip("* ")
            break
    evidence = ""
    in_ev = False
    for line in lines:
        s = line.strip()
        if "\u5173\u952e\u4f9d\u636e" in s or (s.startswith("###") and "2." in s):
            in_ev = True
            continue
        if in_ev:
            if not s:
                continue
            if s.startswith("###") or ("3." in s and "\u5f85\u6f84\u6e05" in s):
                break
            if s.startswith("-") or s.startswith("*"):
                evidence = s.lstrip("-* ").strip()
                break
            if "\u672a\u53d1\u73b0" in s or "\u65e0\u660e\u663e" in s:
                evidence = s.strip("* ")
                break
    parts = []
    if stability:
        parts.append(stability)
    if evidence:
        if len(evidence) > 120:
            evidence = evidence[:117] + "..."
        parts.append("\u5173\u952e\u4f9d\u636e\uff1a" + evidence)
    return "\uff1b".join(parts) if parts else ""


def fetch_from_supabase():
    """Query Supabase and return list of session dicts."""
    sys.path.insert(0, str(BASE_DIR.parent))
    import config
    from supabase import create_client

    client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    result = client.table("output_files").select("*").execute()

    with open(RAW_EXPORT, "w", encoding="utf-8") as f:
        json.dump(result.data, f, ensure_ascii=False, indent=2)
    print("  [OK] Fetched {} records from Supabase".format(len(result.data)))
    return result.data


def build_new_rows(records):
    """Convert Supabase records into CSV rows (no annotations)."""
    rows = []
    for rec in records:
        cj = rec.get("content_json")
        if not cj or not isinstance(cj, dict):
            continue

        filename = rec["filename"]

        lie_idx = cj.get("lie_index")
        if lie_idx is None:
            lie_idx = cj.get("final_report", {}).get("lie_index", None)
        if lie_idx is None:
            lie_idx = 0

        facts = cj.get("facts_table", []) or cj.get("current_facts", [])
        claimed_job = ""
        if isinstance(facts, list):
            for f_item in facts:
                if isinstance(f_item, dict) and f_item.get("slot") in ("occupation", "role"):
                    claimed_job = f_item.get("content", "")
                    break
        if not claimed_job:
            rd = cj.get("round_records", [])
            if rd:
                claimed_job = rd[0].get("user_input", "")[:50]

        rd = cj.get("round_records", [])
        dl = []
        for r_item in rd:
            ui = r_item.get("user_input", "")
            af = r_item.get("ai_followup", "")
            if ui:
                dl.append("[User] " + ui)
            if af:
                dl.append("[AI] " + af)
        dialogue = "\n".join(dl)

        report = cj.get("final_report", {}) or {}
        rt = report.get("report_text", "")
        system_reason = extract_system_reason(rt)

        rows.append({
            "filename": filename,
            "claimed_job": claimed_job,
            "true_label": cj.get("identity_label", ""),
            "valid": "",
            "dialogue": dialogue,
            "system_score": round(float(lie_idx), 1),
            "system_label": "safe" if lie_idx < 25 else "risk",
            "system_reason": system_reason,
            "hit": "",
            "note": "",
        })
    rows.sort(key=lambda x: x["filename"])
    return rows


def load_existing_annotations(csv_path):
    """Read existing CSV and return dict keyed by filename."""
    if not csv_path.exists():
        return {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {r["filename"]: r for r in reader}


def main():
    print("Step 1/2: Fetching from Supabase...")
    records = fetch_from_supabase()

    print("Step 2/2: Merging with existing annotations...")
    new_rows = build_new_rows(records)
    old_map = load_existing_annotations(EXISTING_CSV)

    merged = []
    preserved = 0
    new_count = 0
    for r in new_rows:
        fn = r["filename"]
        if fn in old_map:
            old = old_map[fn]
            r["true_label"] = old.get("true_label", "")
            r["valid"] = old.get("valid", "")
            r["note"] = old.get("note", "")
            r["hit"] = old.get("hit", "")
            preserved += 1
        else:
            new_count += 1
        merged.append(r)

    fieldnames = [
        "filename", "claimed_job", "true_label", "valid", "dialogue",
        "system_score", "system_label", "system_reason", "hit", "note",
    ]
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    print()
    print("  [OK] Merged: {} total rows".format(len(merged)))
    print("       Preserved annotations: {}".format(preserved))
    print("       New unannotated rows: {}".format(new_count))
    print()
    print("  Next:")
    print("   1. Open the CSV and fill true_label / valid for new rows")
    print("   2. Run: python benchmark/run_benchmark.py")


if __name__ == "__main__":
    main()