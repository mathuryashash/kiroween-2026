"""tests/test_ablate.py - hunk splitting and single-hunk reverts (no trials needed)."""
from harness.ablate import apply_patch_except_hunk, split_diff_into_hunks

BEFORE = "def f(x):\n    a = x + 1\n    b = 2\n    c = 3\n    d = 4\n    return a + b + c + d\n"
AFTER = "def f(x):\n    a = x + 10\n    b = 2\n    c = 3\n    d = 40\n    e = 5\n    return a + b + c + d\n"


def test_two_separate_edits_are_two_hunks():
    hunks = split_diff_into_hunks(BEFORE, AFTER)
    assert len(hunks) == 2
    assert "-    a = x + 1\n" in hunks[0]["hunk_text"] and "+    a = x + 10\n" in hunks[0]["hunk_text"]
    assert hunks[1]["lines_removed"] == 1 and hunks[1]["lines_added"] == 2


def test_reverting_one_hunk_keeps_the_other():
    only_second = apply_patch_except_hunk(BEFORE, AFTER, 0)
    assert "a = x + 1\n" in only_second and "d = 40" in only_second and "e = 5" in only_second
    only_first = apply_patch_except_hunk(BEFORE, AFTER, 1)
    assert "a = x + 10" in only_first and "d = 4\n" in only_first and "e = 5" not in only_first


def test_identical_files_have_no_hunks():
    assert split_diff_into_hunks(BEFORE, BEFORE) == []


def test_pure_insertion_and_deletion():
    after = BEFORE.replace("    b = 2\n", "")
    assert apply_patch_except_hunk(BEFORE, after, 0) == BEFORE
    after = BEFORE.replace("    c = 3\n", "    c = 3\n    c2 = 6\n")
    assert apply_patch_except_hunk(BEFORE, after, 0) == BEFORE
