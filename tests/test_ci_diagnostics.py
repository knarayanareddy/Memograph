import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_annotator(log: Path) -> list[str]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "annotate_mypy.py"),
            str(log),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def test_annotate_mypy_emits_escaped_error_annotations(tmp_path: Path) -> None:
    log = tmp_path / "mypy.log"
    log.write_text(
        "src/memograph/example.py:12:3: error: Bad 100% thing [arg-type]\n"
        "note: some context that is not an error\n"
        "src/memograph/example.py:13:1: error: Second problem [assignment]\n",
        encoding="utf-8",
    )

    assert run_annotator(log) == [
        "::error title=mypy::src/memograph/example.py:12:3: error: Bad 100%25 thing [arg-type]",
        "::error title=mypy::src/memograph/example.py:13:1: error: Second problem [assignment]",
    ]


def test_annotate_mypy_reports_extra_error_lines(tmp_path: Path) -> None:
    log = tmp_path / "mypy.log"
    lines = [
        f"src/memograph/example.py:{i}:1: error: problem {i} [assignment]" for i in range(1, 13)
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    output = run_annotator(log)
    assert len(output) == 11
    assert all(line.startswith("::error title=mypy::") for line in output[:10])
    assert output[10] == (
        "::notice title=mypy::2 additional mypy errors are in the uploaded artifact."
    )
