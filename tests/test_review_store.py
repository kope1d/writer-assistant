from pathlib import Path

from tools.review_store import ReviewStore


def test_review_store_records_rereview_issue_delta(tmp_path: Path):
    store = ReviewStore(tmp_path, "demo")
    store.save(
        "ch_001",
        {
            "score": 70,
            "issue_details": [
                {"id": "issue_keep", "dimension": "pace", "summary": "节奏拖沓"},
                {"id": "issue_fixed", "dimension": "logic", "summary": "动机缺失"},
            ],
        },
    )

    store.save(
        "ch_001",
        {
            "score": 82,
            "issue_details": [
                {"id": "issue_keep", "dimension": "pace", "summary": "节奏拖沓"},
                {"id": "issue_new", "dimension": "voice", "summary": "语气漂移"},
            ],
        },
    )

    delta = store.load("ch_001")["issue_delta"]
    assert [item["id"] for item in delta["resolved"]] == ["issue_fixed"]
    assert [item["id"] for item in delta["remaining"]] == ["issue_keep"]
    assert [item["id"] for item in delta["new"]] == ["issue_new"]


def test_review_merges_fact_arbitration_issues_without_duplicates(tmp_path: Path):
    store = ReviewStore(tmp_path, "demo")
    store.save_fact_arbitration(
        "ch_001",
        [
            {
                "severity": "warning",
                "category": "continuity_fact",
                "description": "正文记录了「青铜怀表」（物品获得），但本章结算未体现",
                "suggestion": "补上这条事实",
                "evidence": {"quote": "青铜怀表"},
            }
        ],
    )

    store.save(
        "ch_001",
        {
            "score": 80,
            "issue_details": [
                {"dimension": "pace", "summary": "节奏拖沓"},
            ],
        },
    )

    record = store.load("ch_001")
    summaries = [item["summary"] for item in record["issue_details"]]
    assert "节奏拖沓" in summaries
    assert any("青铜怀表" in item["summary"] for item in record["issue_details"])
    # 二次审稿：仲裁 issue 去重不翻倍
    store.save(
        "ch_001",
        {
            "score": 85,
            "issue_details": [
                {"dimension": "pace", "summary": "节奏拖沓"},
            ],
        },
    )
    record = store.load("ch_001")
    assert sum(1 for item in record["issue_details"] if "青铜怀表" in item["summary"]) == 1


def test_fact_arbitration_record_round_trip(tmp_path: Path):
    store = ReviewStore(tmp_path, "demo")
    path = store.save_fact_arbitration("ch_002", [{"category": "continuity_fact", "description": "x"}])

    assert path.name == "ch_002.facts.json"
    issues = store._load_fact_arbitration("ch_002")  # noqa: SLF001
    assert len(issues) == 1
    assert issues[0]["dimension"] == "continuity_fact"
    assert store._load_fact_arbitration("ch_999") == []  # noqa: SLF001
