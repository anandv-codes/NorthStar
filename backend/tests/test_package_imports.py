import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_import_check(lines: list[str]) -> None:
    subprocess.run([sys.executable, "-c", "\n".join(lines)], cwd=REPO_ROOT, check=True)


def test_chat_contracts_import_does_not_load_orchestrator():
    _run_import_check(
        [
            "import sys",
            "import backend.app.domain.chat.routing_contracts",
            'assert "backend.app.domain.chat.orchestrator" not in sys.modules',
            'assert "backend.app.infrastructure.llm.gemini_client" not in sys.modules',
        ]
    )


def test_routing_contracts_import_does_not_load_orchestrator():
    _run_import_check(
        [
            "import sys",
            "import backend.app.domain.routing.base",
            "import backend.app.domain.routing.contracts",
            'assert "backend.app.domain.routing.orchestrator" not in sys.modules',
            'assert "backend.app.domain.chat.orchestrator" not in sys.modules',
            'assert "backend.app.infrastructure.llm.gemini_client" not in sys.modules',
        ]
    )


def test_scheduling_package_exports_remain_available():
    from backend.app.domain.recall.scheduling import AnkiScheduler, SystemClock

    assert AnkiScheduler.__name__ == "AnkiScheduler"
    assert SystemClock.__name__ == "SystemClock"
