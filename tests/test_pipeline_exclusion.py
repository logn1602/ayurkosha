"""Tests the source-exclusion switches in src/ingestion/pipeline.py.

Runs ingestion over a temp folder with embed=False, with the store saves stubbed
so the real data/cache indexes are never touched.

Run: python -m pytest tests/test_pipeline_exclusion.py
"""

import pytest

from config.settings import settings
from src.ingestion import bm25_store, parent_store, pipeline

FILES = {
    "charaka_samhita_test.txt": "Charaka text about fever and its treatment. ",
    "sushruta_samhita_test.txt": "Sushruta text about cough and its treatment. ",
    "ashtanga_hridaya_srikantha_murthy_vol1.txt": "Garbled OCR text layer for testing purposes. ",
    "ashtanga_hridaya_sanskrit_commentaries.txt": "Sanskrit commentary text for testing purposes. ",
    "ashtanga_hridaya_vidyanath_illustrated.txt": "Dinacarya: brushing the teeth in the morning. ",
}
FLAGS = ("exclude_charaka", "exclude_ah_srikantha_murthy", "exclude_ah_sanskrit_commentaries")


def _run(tmp_path, monkeypatch, **flags):
    for name, text in FILES.items():
        (tmp_path / name).write_text(text * 5)
    saved = {}
    monkeypatch.setattr(parent_store, "save_parent_store", lambda store, *a, **k: saved.setdefault("parents", store))
    monkeypatch.setattr(bm25_store, "save_bm25_index", lambda index, *a, **k: saved.setdefault("bm25", index))
    for flag in FLAGS:
        monkeypatch.setattr(settings, flag, flags.get(flag, True))
    stats = pipeline.run_ingestion(data_dir=tmp_path, embed=False)
    return stats, {c["metadata"]["source"] for c in saved["bm25"].chunks}


def test_defaults_exclude_charaka_and_both_ah_volumes(tmp_path, monkeypatch):
    stats, sources = _run(tmp_path, monkeypatch)
    assert stats["excluded_files"] == 3 and stats["files"] == 2
    assert sources == {"sushruta_samhita_test.txt", "ashtanga_hridaya_vidyanath_illustrated.txt"}


@pytest.mark.parametrize("flag, filename", [
    ("exclude_charaka", "charaka_samhita_test.txt"),
    ("exclude_ah_srikantha_murthy", "ashtanga_hridaya_srikantha_murthy_vol1.txt"),
    ("exclude_ah_sanskrit_commentaries", "ashtanga_hridaya_sanskrit_commentaries.txt"),
])
def test_each_flag_controls_only_its_source(tmp_path, monkeypatch, flag, filename):
    stats, sources = _run(tmp_path, monkeypatch, **{flag: False})
    assert filename in sources
    assert stats["excluded_files"] == 2


def test_excluded_reason_names_the_flag(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setattr(settings, flag, True)
    assert pipeline.excluded_reason("ashtanga_hridaya_srikantha_murthy_vol1.pdf").startswith("exclude_ah_srikantha_murthy")
    assert pipeline.excluded_reason("ashtanga_hridaya_vidyanath_illustrated.pdf") is None
    assert pipeline.excluded_reason("api_all_volume.pdf") is None
