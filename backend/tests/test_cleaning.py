"""
Unit tests for document cleaning (v3): line join, header drop, retention,
doc-type presets, financial preservation, OCR column-fragment join.
"""
import pytest

from src.ingestion.cleaning import (
    CLEANING_VERSION,
    CleaningConfig,
    clean_text,
    clean_document,
    get_config_for_doc_type,
)


def test_cleaning_version_is_v3():
    assert CLEANING_VERSION == "v3"


def test_join_continuation_lines_four_fragments():
    raw = "He walked\ninto the\nroom and\nsat down."
    out = clean_text(raw)
    assert "He walked into the room and sat down." in out
    assert out.count("\n") < 2


def test_join_continuation_lines_sentence_end_not_joined():
    raw = "First sentence is here and it ends properly.\nSecond sentence starts here and continues with more."
    out = clean_text(raw)
    assert "First sentence" in out
    assert "Second sentence" in out
    assert "First sentence. Second" not in out


def test_header_like_line_dropped():
    raw = "iiiIERFUL BILLIONAIRE,\n- EX SCANDAL THAT UNDID HIM\n\nSome real body text here that is long enough to be kept."
    out = clean_text(raw)
    assert "iiiIERFUL BILLIONAIRE" not in out
    assert "Some real body text" in out


def test_retention_ocr_style_blob_removes_at_least_five_percent():
    lines = [
        "iiiIERFUL BILLIONAIRE,",
        "- EX SCANDAL THAT UNDID HIM,",
        "THE JUSTICE THAT MONEY CAN BUY:",
        "",
        "Page 1 of 10",
        "Page 1 of 10",
        ".,,stigation had taken place",
        "jut, at that time",
        "irs had been launched",
        "This is the only line that is clearly real content and long enough to survive.",
    ]
    raw = "\n".join(lines)
    cleaned = clean_text(raw)
    original_len = len(raw)
    cleaned_len = len(cleaned)
    assert original_len > 0
    assert cleaned_len < 0.95 * original_len, (
        f"Expected <95% retained (5%+ removal); got {cleaned_len}/{original_len} = {100*cleaned_len/original_len:.1f}% retained"
    )


def test_line_edge_punctuation_stripped():
    raw = ".,,stigation had taken place and continued."
    out = clean_text(raw)
    assert out.startswith("stigation") or "stigation" in out
    assert not out.startswith(".,,")


def test_clean_document_attaches_metrics():
    doc = {"doc_id": "x", "text": "Short.\n\nBody here."}
    out = clean_document(doc)
    assert out["cleaning_applied"] is True
    assert "original_length" in out and "cleaned_length" in out and "cleaning_ratio" in out
    assert out["text"] == clean_text(doc["text"])


def test_config_disable_join_keeps_lines_split():
    raw = "He walked down the street slowly and then stopped.\nInto the room he went without looking back.\nThe room was dark and cold and very quiet."
    cfg = CleaningConfig(join_continuation_lines=False)
    out = clean_text(raw, config=cfg)
    assert "He walked" in out
    assert out.count("\n") >= 2


# --- v3: doc-type presets, financial preservation, OCR fragment join ---


def test_financial_row_preservation():
    raw = "OMB No. 3235-0106\nPage 1 of 3\nNIA None (or less than $1,001) Dividends.Capital Gain $2,501 - $5,000.\nOMB Approval something"
    cfg = CleaningConfig(conservative_financial=True)
    out = clean_text(raw, config=cfg)
    assert "NIA None" in out
    assert "Dividends.Capital Gain" in out or "2,501" in out
    assert "OMB No." not in out or "3235" not in out
    assert "Page 1 of 3" not in out


def test_financial_row_preservation_via_clean_document():
    doc = {
        "doc_id": "fd1",
        "doc_type": "financial_document",
        "text": "Page 2 of 2\nNIA None (or less than $1,001) Dividends.Capital Gain $2,501 - $5,000.",
    }
    out = clean_document(doc)
    assert "NIA None" in out["text"]
    assert "Page 2 of 2" not in out["text"]
    assert out["cleaning_applied"] is True
    assert "cleaned_length" in out


def test_ocr_fragment_joining():
    raw = "The inv\nestigation had begun and the case was closed."
    cfg = CleaningConfig(join_ocr_column_fragments=True)
    out = clean_text(raw, config=cfg)
    assert "inv " in out and "estigation" in out
    assert " inv\nestigation" not in out


def test_ocr_fragment_joining_international():
    raw = "The int\nernational court ruled."
    cfg = CleaningConfig(join_ocr_column_fragments=True)
    out = clean_text(raw, config=cfg)
    assert "int " in out and "ernational" in out


def test_ocr_fragment_joining_inserts_space():
    raw = "criminal\nirs had been launched."
    cfg = CleaningConfig(join_ocr_column_fragments=True)
    out = clean_text(raw, config=cfg)
    assert "criminal irs" in out
    assert "criminalirs" not in out


def test_preset_financial_document():
    cfg = get_config_for_doc_type("financial_document")
    assert cfg.join_continuation_lines is False
    assert cfg.join_ocr_column_fragments is False
    assert cfg.conservative_financial is True
    assert cfg.strip_line_edge_punctuation is False


def test_preset_book_excerpt():
    cfg = get_config_for_doc_type("book_excerpt")
    assert cfg.join_continuation_lines is True
    assert cfg.join_ocr_column_fragments is True
    assert cfg.conservative_financial is False
    assert cfg.strip_line_edge_punctuation is True


def test_preset_court_filing():
    cfg = get_config_for_doc_type("court_filing")
    assert cfg.join_continuation_lines is True
    assert cfg.join_ocr_column_fragments is False
    assert cfg.conservative_financial is False


def test_preset_letter():
    cfg = get_config_for_doc_type("letter")
    assert cfg.join_continuation_lines is True
    assert cfg.join_ocr_column_fragments is False
    assert cfg.conservative_financial is False


def test_preset_biography():
    cfg = get_config_for_doc_type("biography")
    assert cfg.join_continuation_lines is True
    assert cfg.join_ocr_column_fragments is False
    assert cfg.conservative_financial is False


def test_preset_media_article():
    cfg = get_config_for_doc_type("media_article")
    assert cfg.join_continuation_lines is True
    assert cfg.join_ocr_column_fragments is False
    assert cfg.conservative_financial is False


def test_preset_other_same_as_media_article():
    """doc_type=other gets same cleaning preset as media_article (no free pass)."""
    cfg_other = get_config_for_doc_type("other")
    cfg_media = get_config_for_doc_type("media_article")
    assert cfg_other.join_continuation_lines == cfg_media.join_continuation_lines
    assert cfg_other.join_ocr_column_fragments == cfg_media.join_ocr_column_fragments
    assert cfg_other.conservative_financial == cfg_media.conservative_financial
    assert cfg_other.strip_line_edge_punctuation == cfg_media.strip_line_edge_punctuation


def test_preset_unknown_returns_default():
    cfg = get_config_for_doc_type(None)
    assert cfg.join_continuation_lines is True
    assert cfg.join_ocr_column_fragments is False
    assert cfg.conservative_financial is False
    cfg2 = get_config_for_doc_type("unknown_type")
    assert cfg2.join_continuation_lines is True
