import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarkers.cli import dedupe_results


def row(case_id, tool_id, status, category="scraping"):
    return {
        "case": {"category": category, "id": case_id},
        "tool": {"id": tool_id},
        "status": status,
    }


def test_later_run_replaces_earlier_for_same_pair():
    old = row("a", "t", "pass")
    new = row("a", "t", "fail")
    kept, dropped = dedupe_results([old, new])
    assert kept == [new]
    assert dropped == [old]


def test_skip_never_shadows_executed_result():
    paid = row("a", "t", "pass")
    skip = row("a", "t", "skip")
    kept, dropped = dedupe_results([paid, skip])
    assert kept == [paid]
    assert dropped == [skip]


def test_executed_result_replaces_earlier_skip():
    skip = row("a", "t", "skip")
    ran = row("a", "t", "pass")
    kept, dropped = dedupe_results([skip, ran])
    assert kept == [ran]
    assert dropped == [skip]


def test_skip_kept_when_it_is_the_only_row():
    skip = row("a", "t", "skip")
    kept, dropped = dedupe_results([skip])
    assert kept == [skip]
    assert dropped == []


def test_distinct_pairs_pass_through_in_order():
    rows = [row("a", "t1", "pass"), row("b", "t1", "pass"), row("a", "t2", "timeout")]
    kept, dropped = dedupe_results(rows)
    assert kept == rows
    assert dropped == []
