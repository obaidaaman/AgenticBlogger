"""
test_sandbox.py — Standalone test suite for Code Sandbox and LangGraph integration.
"""

import asyncio
from core.nodes.code_sandbox import (
    extract_python_code,
    run_code_in_sandbox,
    code_verifier_node,
    route_after_code_check,
)
from core.agent import app
from main import app as fastapi_app


async def run_tests():
    print("=" * 60)
    print("1. TESTING CODE SANDBOX RUNNER")
    print("=" * 60)

    # Test 1: Valid python code
    valid_code = "a = 10\nb = 20\nassert a + b == 30"
    ok, err = await run_code_in_sandbox(valid_code)
    assert ok, f"Valid code should pass, got: {err}"
    print("  ✓ Valid code: PASSED")

    # Test 2: Syntax error (caught by AST parse)
    syntax_error_code = "def broken(\n    pass"
    ok, err = await run_code_in_sandbox(syntax_error_code)
    assert not ok, "Syntax error should fail"
    assert "SyntaxError" in err, f"Expected SyntaxError, got: {err}"
    print(f"  ✓ Syntax error caught: {err}")

    # Test 3: Runtime error
    runtime_error_code = "x = 1 / 0"
    ok, err = await run_code_in_sandbox(runtime_error_code)
    assert not ok, "Division by zero should fail"
    assert "ZeroDivisionError" in err, f"Expected ZeroDivisionError, got: {err}"
    print(f"  ✓ Runtime error caught: {err}")

    # Test 4: Infinite loop / Timeout
    infinite_loop = "while True:\n    pass"
    ok, err = await run_code_in_sandbox(infinite_loop, timeout=1.0)
    assert not ok, "Infinite loop should fail"
    assert "timed out" in err, f"Expected timeout, got: {err}"
    print(f"  ✓ Infinite loop timeout caught: {err}")

    print("\n" + "=" * 60)
    print("2. TESTING CODE VERIFIER NODE (GRAPH LOGIC)")
    print("=" * 60)

    # Scenario A: Section with no code (pure prose)
    state_no_code = {
        "sections": [(1, "## Introduction\nThis section has only technical prose, no code.")]
    }
    res_no_code = await code_verifier_node(state_no_code)
    assert res_no_code["code_errors"] == [], "Prose should have 0 code errors"
    assert route_after_code_check(res_no_code) == "reducer", "Should route to reducer"
    print("  ✓ Prose-only section: PASSED (skips straight to reducer)")

    # Scenario B: Section with clean code
    state_clean_code = {
        "sections": [
            (
                1,
                "## Implementation\nHere is how to compute sum:\n```python\nnums = [1, 2, 3]\nsum_total = sum(nums)\n```",
            )
        ]
    }
    res_clean = await code_verifier_node(state_clean_code)
    assert res_clean["code_errors"] == [], "Clean code should have 0 errors"
    assert route_after_code_check(res_clean) == "reducer", "Clean code should route to reducer"
    print("  ✓ Clean code section: PASSED (routes to reducer)")

    # Scenario C: Section with broken code
    state_broken_code = {
        "sections": [
            (
                1,
                "## Faulty Implementation\n```python\nd = {'key': 1}\nprint(d['unknown_key'])\n```",
            )
        ]
    }
    res_broken = await code_verifier_node(state_broken_code)
    assert len(res_broken["code_errors"]) == 1, "Expected 1 error for KeyError"
    assert "KeyError" in res_broken["code_errors"][0]["error"]
    assert route_after_code_check(res_broken) == "self_healing", "Broken code should route to self_healing"
    print(f"  ✓ Broken code section: PASSED (triggers self_healing loop)")

    # Scenario D: Max retries safety
    res_broken["code_healing_retries"] = 2
    assert route_after_code_check(res_broken) == "reducer", "Max retries should route to reducer"
    print("  ✓ Max retries guard: PASSED (prevents infinite loop, moves to reducer)")

    print("\n" + "=" * 60)
    print("3. TESTING LANGGRAPH TOPOLOGY & FASTAPI")
    print("=" * 60)

    graph_nodes = list(app.get_graph().nodes.keys())
    print(f"  Graph Nodes: {graph_nodes}")
    expected_nodes = {"router", "research", "orchestrator", "worker", "code_verifier", "self_healing", "reducer", "human_review"}
    assert expected_nodes.issubset(set(graph_nodes)), "Missing nodes in graph"
    print("  ✓ LangGraph topology: VERIFIED")

    routes = [r.path for r in fastapi_app.routes]
    for r in ["/api/v1/signup", "/api/v1/login", "/api/v1/refresh", "/api/v1/logout", "/api/v1/ws/{thread_id}"]:
        assert r in routes, f"Missing route {r}"
    print("  ✓ FastAPI routes: VERIFIED")

    # Brief pause to let any background async subprocess handles close cleanly
    await asyncio.sleep(0.1)

    print("\n" + "=" * 60)
    print(">>> ALL TESTS COMPLETED SUCCESSFULLY! <<<")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
