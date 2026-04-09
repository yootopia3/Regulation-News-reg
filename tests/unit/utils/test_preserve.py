"""Unit tests for src.utils.preserve.preserve_selected_keys."""
from src.utils.preserve import PRESERVED_KEYS, preserve_selected_keys


def test_preserved_keys_constant():
    assert PRESERVED_KEYS == ("pdf_url",)


def test_case_a_merges_pdf_url_into_new_dict():
    old = {"pdf_url": "u", "risk_level": "HIGH"}
    new = {"risk_level": "LOW", "risk_score": 20}
    assert preserve_selected_keys(old, new) == {
        "risk_level": "LOW",
        "risk_score": 20,
        "pdf_url": "u",
    }


def test_case_b_new_is_none_builds_carry_dict():
    old = {"pdf_url": "u"}
    assert preserve_selected_keys(old, None) == {"pdf_url": "u"}


def test_case_c_old_is_none_returns_new():
    new = {"risk_level": "LOW"}
    assert preserve_selected_keys(None, new) == {"risk_level": "LOW"}


def test_case_d_no_preserved_keys_in_old_returns_new():
    old = {"risk_level": "HIGH"}
    new = {"risk_level": "LOW"}
    assert preserve_selected_keys(old, new) == {"risk_level": "LOW"}


def test_case_e_empty_string_not_carried():
    old = {"pdf_url": ""}
    assert preserve_selected_keys(old, None) is None


def test_case_f_new_value_wins_when_preserved_key_present():
    old = {"pdf_url": "u"}
    new = {"pdf_url": "v"}
    assert preserve_selected_keys(old, new) == {"pdf_url": "v"}


def test_case_g_old_not_dict_defensive():
    assert preserve_selected_keys("not a dict", {"x": 1}) == {"x": 1}


def test_case_h_only_preserved_keys_carried_extras_dropped():
    old = {"pdf_url": "u", "extra": 1}
    new = {"analysis_status": "ANALYZED"}
    assert preserve_selected_keys(old, new) == {
        "analysis_status": "ANALYZED",
        "pdf_url": "u",
    }
