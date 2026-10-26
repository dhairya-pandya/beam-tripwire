from tripwire.variants import mutate_test_patch

PATCH = (
    "--- a/tests/test_x.py\n"
    "+++ b/tests/test_x.py\n"
    "@@ -1,2 +1,6 @@\n"
    " import pkg\n"
    "+def test_value():\n"
    "+    assert pkg.f(2) == 4\n"
    "+    assert pkg.name() == \"alpha\"\n"
    "+    x = 1\n"
)


def test_mutates_first_literal_assertion_only():
    out, info = mutate_test_patch(PATCH)
    assert "+    assert pkg.f(2) == 5\n" in out
    assert "+    assert pkg.name() == \"alpha\"\n" in out
    assert info == {"file": "tests/test_x.py", "original": "4", "mutated": "5",
                    "line": "    assert pkg.f(2) == 4"}


def test_string_literal_mutation_keeps_quotes():
    patch = PATCH.replace("assert pkg.f(2) == 4", "assert pkg.g() == x")
    out, info = mutate_test_patch(patch)
    assert '+    assert pkg.name() == "alpha_v2"\n' in out
    assert info["original"] == '"alpha"' and info["mutated"] == '"alpha_v2"'


def test_skips_context_and_removed_lines():
    patch = (
        "--- a/t.py\n+++ b/t.py\n@@ -1 +1 @@\n"
        "-    assert a == 1\n"
        "     assert b == 2\n"
        "+    assert c == 3\n"
    )
    out, info = mutate_test_patch(patch)
    assert "+    assert c == 4\n" in out and "-    assert a == 1\n" in out
    assert info["file"] == "t.py"


def test_no_literal_assertion_returns_none():
    assert mutate_test_patch("--- a/t.py\n+++ b/t.py\n@@\n+    assert f(x)\n") is None


def test_negative_and_float_literals():
    p = "--- a/t.py\n+++ b/t.py\n@@\n+    assert f() == -1.5\n"
    out, info = mutate_test_patch(p)
    assert info["mutated"] == "-0.5"


def test_rigged_line_shows_the_mutated_value():
    from tripwire.variants import Variant

    v = Variant("x", "r", "tests/t.py", "200", "201", "    assert r.status_code == 200", "", [])
    assert v.rigged_line == "    assert r.status_code == 201"
