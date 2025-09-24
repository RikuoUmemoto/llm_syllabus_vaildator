import argparse, json, sys, os, csv
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.validator import validate_text


def build_text(item: dict) -> str:
    """入力レコードから LLM に渡す生テキスト（実験用: 加工なし）"""
    parts = []

    # 成績評価（そのまま）
    g = (item.get("overview_structured", {}) or {}).get("grading")
    if isinstance(g, str) and g.strip():
        parts.append(g.strip())

    # 週次計画（そのまま）
    tp = item.get("teaching_plan") or []
    for w in tp:
        if isinstance(w, dict):
            week = str(w.get("week", "")).strip()
            content = str(w.get("content", "")).strip()
            parts.append(f"{week} {content}".strip())

    # 概要（そのまま）
    outline = (item.get("overview_structured", {}) or {}).get("outline")
    if isinstance(outline, str) and outline.strip():
        parts.append(outline.strip())

    return "\n".join(parts) if parts else (item.get("title") or "")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", dest="out", required=True)
    p.add_argument("--csv", dest="csv", required=True)
    p.add_argument("--min-weeks", dest="min_weeks", type=int, default=14)
    args = p.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    total = len(data)

    for i, item in enumerate(data):
        text = item.get("text") or build_text(item)

        payload = {
            "text": text,
            "use_llm": True,
            "provider": item.get("provider", "ollama"),
            "model": item.get("model", "elyza:8b-q8"),
            "min_weeks": args.min_weeks,
        }

        out = validate_text(**payload)
        results.append({"input": item, "output": out})

        if (i + 1) % 10 == 0 or (i + 1) == total:
            print(f"[{i+1}/{total}] done", file=sys.stderr)

    # JSON出力
    with open(args.out, "w", encoding="utf-8") as fo:
        json.dump({"result": results}, fo, ensure_ascii=False, indent=2)

    # CSV出力（LLMの結果を素直に反映）
    cols = [
        "title","teacher","Quiz","Exam","Report","Project","Participation","Other",
        "total","is100","weeks","alerts"
    ]
    with open(args.csv, "w", encoding="utf-8", newline="") as fc:
        w = csv.writer(fc)
        w.writerow(cols)
        for r in results:
            inp = r["input"]
            out = r["output"]
            ev = out["result"]["evaluation_by_normalized_name"]
            total_p = out["result"]["evaluation_total_percent"]
            is100 = out["result"]["evaluation_total_is_100"]
            weeks = out["result"]["detected_week_count"]
            alerts = " | ".join(a["message"] for a in out.get("alerts", []))
            w.writerow([
                inp.get("title",""),
                inp.get("teacher",""),
                ev.get("Quiz",0),
                ev.get("Exam",0),
                ev.get("Report",0),
                ev.get("Project",0),
                ev.get("Participation",0),
                ev.get("Other",0),
                total_p,
                "TRUE" if is100 else "FALSE",
                weeks,
                alerts
            ])


if __name__ == "__main__":
    main()
