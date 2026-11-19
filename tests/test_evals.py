from evals.run_evals import run_checks


def test_feasibility_edit_isolation_and_compliance(conn, topics, csv_path):
    lines = run_checks(conn, topics, str(csv_path))
    assert lines == [
        "feasibility: pass",
        "correctness of edits: pass",
        "grounding and compliance: pass",
    ]
