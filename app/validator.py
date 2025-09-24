# app/validator.py
from __future__ import annotations
import json
import math
import re
import requests
from typing import Dict, Any, List, Tuple, Optional
from string import Template

# ====== 入力安定化（最小限）======
Z2H = str.maketrans("０１２３４５６７８９％．，：；（）　", "0123456789%.,:;() ")
DASHES = r"〜～ｰ—−–"

def _z2h(s: str) -> str:
    return (s or "").translate(Z2H)

def _normalize_text_for_weeks(s: str) -> str:
    t = _z2h(s or "")
    for d in DASHES:
        t = t.replace(d, "~")
    return t


# ====== 1st pass: 抽出用プロンプト（LLMに全責任）======
SYSTEM_PROMPT = """
あなたは大学シラバスの情報抽出アシスタントです。
必ず**与えられたテキストのみ**に基づいて判断し、次の厳格なJSONのみを返してください。

出力スキーマ:
{
  "evaluations": [
    {
      "raw_name": "文字列",
      "percent": 数値,
      "normalized_label": "Quiz|Exam|Report|Participation|Presentation|Assignment|Project|Other",
      "confidence": 数値(0~1)
    }
  ],
  "weeks": {
    "detected_count": 整数,
    "markers": ["根拠として拾った原文の断片を1つ以上"]
  },
  "notes": ["補足（あれば）"]
}

### 判断ルール（厳守）

1. **配点（評価割合）**
   - 「評価対象＋割合（% や割・点換算）」の組み合わせは必ず evaluations に含める。
   - 評価対象の例: 課題, レポート, 小テスト, 中間試験, 期末試験, Final Exam, 出席, Presentation, Project など。
   - 割合表現の例: 40%, ６０％, 六割, 0.6, 60/100, 「６割」など。
   - 0.6, 0.7 のような小数値は必ず百分率に換算して返す（0.6 → 60.0, 0.7 → 70.0）。
   - 評価対象が明示されている限り、それが「60%」でも「70%」でも evaluations に含めなければならない。

   ✅ 配点の例（必ず evaluations に含める）
   - 「課題 40%、期末試験 60%」
   - 「Reports: 30% / Exams: 70%」
   - 「Attendance 10%、Presentations 20%、Final Exam 70%」
   - 「成績評価はレポート６割、試験４割」
   - 「期末 ６０％、課題 ４０％」
   - 「Final exam 0.6、Assignments 0.4」

2. **合否基準（基準点・到達目標）**
   - 「合格」「単位認定」「到達」などを条件にしている場合は evaluations に含めない。
   - 数字が％で書かれていても、評価対象と結びつかず「合格条件」だけを述べている場合は除外する。

   ❌ 合否基準の例（evaluations に含めない）
   - 「合格は60%以上」
   - 「70%以上の得点で単位認定」
   - 「到達目標を60%以上満たすこと」

3. **曖昧な場合**
   - 判断が難しいときは **evaluations に含める**。
   - その上で notes に「合否基準の可能性あり」と明記する。

4. **複数項目**
   - 成績評価の章に複数の配点があれば、**漏れなくすべて evaluations に列挙**する。
   - 抜けがあれば notes に理由を残す。

5. **授業週数の数え方**
   - 授業週数は teaching plan や本文から **LLM が責任を持って**数える。
   - 次のいずれでも欠落がなければ、その回数を `weeks.detected_count` にする：
     - 「1,2,…,14」など数字だけの連番
     - 1行ごとに「<番号> <内容>」の列挙（例: `1 ヒューマンインタフェース概論`）
   - 「第1回〜第13回＋期末（試験・まとめ・Final exam など）」のように最終回が別表記でも、**合計回数**で数える（= 14 として扱う）。
   注意: detected_count と markers の要素数が一致しない場合は不正解とみなす。
   
6. **出力**
   - 数字は **必ず 0〜100 の百分率 (float)** に統一。
   - JSON以外のテキストは一切出さない。
   - 絶対に JSON 以外のテキストを出してはいけません。
   - 返答は JSON のみとします。

7. **配点が明示されていない場合**
   - 割合が書かれていない場合は、evaluations を空リスト [] にする。
   - 評価対象があっても割合が無ければ含めない。

"""



USER_TMPL = """次のシラバス抜粋から、配点（評価割合）と授業週数を抽出して、上記スキーマのJSONで出力してください。
---
{txt}
"""


# ========= 閾値（合格基準）誤カウント防止：LLMガード（LLMに判断を委任） =========
THRESHOLD_GUARD_SYS = """あなたはシラバスの配点抽出を監査するアシスタントです。
与えられた「評価候補(JSON)」の各要素について、次の方針で remove_indices に入れるべきか判断してください。

【定義】
- 配点（評価割合）：評価対象（例：課題・小テスト・中間・期末・試験・レポート・出席・発表・Presentation・Project・Exam など）に「割合/比率/点換算」が明示されているもの。
- 合否基準：合格・単位認定・到達・基準点・ボーダー等の“条件”を述べるもの（例：「合格は60%以上」「70%以上で単位認定」など）。評価対象と結びつかない。

【厳守ルール】
1) 「評価対象＋割合（%・割・0.x・x/100・点換算）」の形式が明確なものは、絶対に remove しない。
   - 例：「期末試験 60%」「課題 40%」「Reports 30% / Exams 70%」「Final exam 0.6」
2) 「合格」「単位認定」「到達」「基準」「ボーダー」など条件表現のみで、評価対象が伴わないものは remove する。
   - 例：「合格は60%以上」「70%以上の得点で単位認定」
3) 曖昧な場合は remove しない（＝残す）。notes に「曖昧（配点の可能性あり）」と書く。
4) 評価対象が明示されていても、その文が「合格」「到達」「認定」などの条件文と直結している場合は remove する。
   - 例：「卒業研究…により評価する。この場合、到達目標を60%以上達成している学生を合格とする。」
   → 「60%以上」は配点ではなく条件なので remove する。

【出力】
JSON のみ：
{
  "remove_indices": [整数...],
  "notes": ["補足"...]
}

【少数例（確認用）】
- OK（残す）： raw_name: "期末試験", percent: 60
- OK（残す）： raw_name: "Final Exam", percent: 0.6
- NG（除外）： raw_name: "合格は60%以上", percent: 60
"""


THRESHOLD_GUARD_USER_TMPL = Template("""評価候補(JSON):
$EVALS_JSON

原文テキスト（参考; 必要に応じて使用）:
---
$TEXT
---

タスク:
- 上記【厳守ルール】に従い、remove_indices と notes を返す。
- 「試験/期末/課題/レポート/出席/発表/Presentation/Project/Exam など評価対象＋割合」は絶対に remove しない。
- 「合格/到達/単位認定/基準/ボーダー」の“条件文”のみは remove する。
- 曖昧な場合は remove しないで notes に理由を記載。

出力は JSON のみ。
""")



# ====== 入力切り出し：評価章を必ず含める & 長文対策 ======
EVAL_KEYS = [
    "成績評価", "評価方法", "評価基準", "成績の評価", "成績", "評価",
    "Grading", "Assessment", "Evaluation", "Grade", "Evaluation criteria", "Grading policy"
]

def _find_last_eval_key_pos(t: str) -> int:
    last = -1
    if not t:
        return -1
    for kw in EVAL_KEYS:
        if re.fullmatch(r"[A-Za-z ].+", kw):
            for m in re.finditer(re.escape(kw), t, flags=re.IGNORECASE):
                last = max(last, m.start())
        else:
            for m in re.finditer(re.escape(kw), t):
                last = max(last, m.start())
    return last

def _slice_for_llm(text: str, max_len: int = 16000,
                   head_len: int = 6000, tail_len: int = 8000,
                   window_radius: int = 6000) -> str:
    t = text or ""
    n = len(t)
    last_pos = _find_last_eval_key_pos(t)
    if last_pos >= 0:
        start = max(0, last_pos - window_radius)
        end = min(n, last_pos + window_radius)
        window = t[start:end]
        head = t[:min(head_len, n)]
        joined = (head + "\n...\n" + window) if start > head_len else window
        return joined[-max_len:] if len(joined) > max_len else joined

    head = t[:min(head_len, n)]
    tail = t[max(0, n - tail_len):]
    merged = head + ("\n...\n" if head and tail else "") + tail
    return merged[-max_len:] if len(merged) > max_len else merged


# ====== LLM 呼び出し ======
def call_ollama(model: str, system: str, user: str) -> str:
    url = "http://127.0.0.1:11434/api/chat"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": "json",
        "stream": False,
        # モデルが対応する範囲で文脈長を拡大（例: 32k）。決定性確保のため temperature=0。
        "options": {
            "num_ctx": 32768,
            "temperature": 0
        }
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=180)
    try:
        data = r.json()
        return data["message"]["content"]
    except Exception:
        return r.text


import re
import json

def _extract_balanced_json(s: str) -> str | None:
    # 最初の '{' から波括弧のネストを数えて 0 に戻った位置までを抜く
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i+1]
    # 最後まで 0 に戻らない＝外側の '}' が欠落している
    return None

def _light_fixups(cleaned: str) -> str:
    import re

    fixed = cleaned

    # 1) 末尾の ",]" や ",}" を修正
    fixed = fixed.replace(",]", "]").replace(",}", "}")

    # 2) weeks の閉じ忘れ:
    #    ... "markers": [ ... ] , "notes": ...  →  ... "markers": [ ... ] }, "notes": ...
    #    「weeks: { ... "markers": ... }」の内側に限定しなくても、この崩れは実質ここでしか出ない想定なので
    fixed = re.sub(
        r'("markers"\s*:\s*\[[^\]]*\])\s*,\s*"notes"',
        r'\1}, "notes"',
        fixed,
        flags=re.DOTALL
    )

    # 3) 行末カンマを安全に除去（..., } / ..., ]）
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

    # 4) notes が無ければ末尾に補完（外側オブジェクト）
    if '"notes"' not in fixed:
        tail = fixed.rstrip()
        if tail.endswith("}"):
            fixed = tail[:-1] + ', "notes": []}'

    # 5) 外側 '}' を落としていたら補う（稀なケース）
    if fixed.count("{") > fixed.count("}"):
        fixed = fixed + "}" * (fixed.count("{") - fixed.count("}"))

    return fixed

def _llm_extract(text: str, provider: str, model: str) -> Dict[str, Any]:
    norm_text = _normalize_text_for_weeks(text or "")
    sliced = _slice_for_llm(
        norm_text,
        max_len=16000,
        head_len=6000,
        tail_len=8000,
        window_radius=6000
    )
    raw = call_ollama(model, SYSTEM_PROMPT, USER_TMPL.format(txt=sliced)) \
        if provider == "ollama" else call_openai(model, SYSTEM_PROMPT, USER_TMPL.format(txt=sliced))

    # 1) まずバランスの取れた JSON を探す
    balanced = _extract_balanced_json(raw)
    if balanced is None:
        # 見つからない場合は {.*} の最大一致で拾ってから修理
        m = re.search(r"\{.*", raw, flags=re.DOTALL)
        if not m:
            raise ValueError(f"LLM output is not valid JSON:\n{raw}")
        candidate = m.group(0)
    else:
        candidate = balanced

    # 2) 軽微な体裁崩れを修理
    candidate = _light_fixups(candidate)

    # 3) パース
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        # 失敗時はデバッグしやすいように本文を出す
        raise ValueError(f"Failed to parse JSON after sanitizing:\n{candidate}") from e


# ====== 閾値ガード（LLMに判断） ======
def _llm_filter_thresholds(
    text: str,
    evals: List[Dict[str, Any]],
    provider: str,
    model: str
) -> Tuple[List[int], List[str]]:
    try:
        user = THRESHOLD_GUARD_USER_TMPL.substitute(
            EVALS_JSON=json.dumps(evals, ensure_ascii=False),
            TEXT=_normalize_text_for_weeks(text)[:6000],
        )
        raw = call_ollama(model, THRESHOLD_GUARD_SYS, user) if provider == "ollama" \
            else call_openai(model, THRESHOLD_GUARD_SYS, user)
        data = json.loads(raw)
        rm = data.get("remove_indices") or []
        notes = data.get("notes") or []
        rm = [int(i) for i in rm if isinstance(i, int) or (isinstance(i, str) and i.isdigit())]
        notes = [str(n) for n in notes if n]
        return rm, notes
    except Exception:
        return [], []


# ====== public API ======
CANON_LABELS = ["Quiz", "Exam", "Report", "Project", "Participation", "Presentation", "Assignment", "Other"]

def _safe_float(x) -> float:
    try:
        s = str(x)
        if not s or s.lower() == "nan":
            return 0.0
        s = _z2h(s)
        s = s.replace("約", "").replace("およそ", "").replace("~", "")
        s = re.sub(r"[^0-9.]", "", s)
        if s == "" or s == ".":
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def validate_text(
    text: str,
    *,
    use_llm: bool,
    provider: str = "ollama",
    model: str = "elyza:8b-q8",
    min_weeks: int = 14,
) -> Dict[str, Any]:
    # 1) 抽出
    data = _llm_extract(text, provider, model)

    evals_in = data.get("evaluations", []) or []
    weeks_in = data.get("weeks", {}) or {}
    llm_notes = list(data.get("notes", []) or [])

    # 2) 閾値ガード（LLMが除外すべきインデックスを返す）
    to_remove, guard_notes = _llm_filter_thresholds(text, evals_in, provider, model)
    llm_notes.extend(guard_notes)
    if to_remove:
        # LLMの判断に従い除外（ルール救済は行わない）
        rmset = set(to_remove)
        evals_in = [ev for idx, ev in enumerate(evals_in) if idx not in rmset]

    # 3) 出力整形（LLM結果を尊重）
    out_evals: List[Dict[str, Any]] = []
    by_norm: Dict[str, float] = {}

    for ev in evals_in:
        raw_name = str(ev.get("raw_name") or "").strip() or "不明"
        percent = _safe_float(ev.get("percent"))
        cand = str(ev.get("normalized_label") or "Other")
        conf = _safe_float(ev.get("confidence"))
        if cand not in CANON_LABELS:
            cand = "Other"
        out_evals.append({
            "raw_name": raw_name,
            "percent": percent,
            "normalized_candidate": cand,
            "normalized_final": cand,
            "confidence": conf,
        })
        by_norm[cand] = round(by_norm.get(cand, 0.0) + percent, 2)

    total = round(sum(e.get("percent", 0.0) for e in out_evals), 2)
    is100 = math.isclose(total, 100.0, abs_tol=0.5)

    detected_week_count = int(weeks_in.get("detected_count", 0) or 0)
    week_markers = [str(x) for x in (weeks_in.get("markers") or []) if x]

    alerts: List[Dict[str, str]] = []
    if not out_evals:
        alerts.append({"type": "warn", "message": "評価割合の記載が抽出できませんでした（LLM出力が空）。"})
    if not is100:
        alerts.append({"type": "flag", "message": f"評価割合の合計が100%ではありません（合計 {total}%）。"})
    if detected_week_count not in {min_weeks, 28}:
        alerts.append({"type": "warn", "message": f"週次計画が {min_weeks} 週/28週に満たない可能性（検出 {detected_week_count} 週）。"})

    result = {
        "evaluations": out_evals,
        "evaluation_total_percent": total,
        "evaluation_total_is_100": bool(is100),
        "evaluation_by_normalized_name": by_norm,
        "detected_week_count": detected_week_count,
        "week_markers": week_markers,
        "llm_notes": llm_notes,
    }
    return {"result": result, "alerts": alerts}
