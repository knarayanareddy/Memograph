from __future__ import annotations

import json

from memograph.cli.memograph_cli import main


def test_cli_end_to_end(tmp_path, capsys):
    def run(*args: str):
        code = main(
            [
                "--base-path",
                str(tmp_path / "store"),
                "--provider",
                "none",
                *args,
            ]
        )
        output = capsys.readouterr().out
        return code, json.loads(output)

    code, status = run("status")
    assert code == 0
    assert status["topics"]["total"] == 0

    code, remembered = run(
        "remember", "project_stack", "Uses FastAPI and SQLite", "--source", "readme"
    )
    assert code == 0
    assert remembered["success"] is True

    code, recalled = run("recall", "What framework?")
    assert code == 0
    assert len(recalled) == 1
    assert recalled[0]["topic_id"] == "project_stack"

    code, index = run("index")
    assert code == 0
    assert "project_stack" in index["index"]

    code, context = run("context", "What framework?")
    assert code == 0
    assert "hints, not ground truth" in context["text"]

    code, dream = run("dream", "--force")
    assert code == 0
    assert dream["status"] == "completed"

    code, pruned = run("prune")
    assert code == 0
    assert pruned["pointers_removed"] == 0

    code, grepped = run("grep", "FastAPI")
    assert code == 0
    assert grepped == []
