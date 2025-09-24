
from app.validator import validate_text
import os

RULES = os.path.join(os.path.dirname(__file__), "..", "app", "assets", "normalize_rules.yaml")

def test_eval_sum_100_rule_only():
    text = "成績評価: 小テスト20%、期末試験30%、平常点50%。"
    res = validate_text(text, use_llm=False, provider="none", model="", min_weeks=14, rules_yaml_path=RULES)
    assert res["result"]["evaluation_total_is_100"] is True

def test_eval_sum_95_flag():
    text = "成績評価: 小テスト20%、期末試験30%、平常点45%。"
    res = validate_text(text, use_llm=False, provider="none", model="", min_weeks=14, rules_yaml_path=RULES)
    assert res["result"]["evaluation_total_is_100"] is False
    assert any('100%' in a['message'] for a in res['alerts'])

def test_weeks_warn_llm_zero():
    text = "成績評価: 小テスト20%、期末試験30%、平常点50%。"
    res = validate_text(text, use_llm=False, provider="none", model="", min_weeks=14, rules_yaml_path=RULES)
    # 週数0→閾値未満で警告
    assert any('週次計画' in a['message'] for a in res['alerts'])
