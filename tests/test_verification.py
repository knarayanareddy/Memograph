from __future__ import annotations

from memograph.config import ConfidenceLevel
from memograph.models import MemoryFact, TopicFile
from memograph.verification import VerificationEngine


async def test_verification_engine(tmp_path):
    existing = tmp_path / "src" / "main.py"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("print('ok')\n", encoding="utf-8")
    topic = TopicFile(
        topic_id="project",
        topic_name="Project",
        facts=[
            MemoryFact(
                content="main.py exists",
                confidence=ConfidenceLevel.OBSERVED,
                source="s",
                verification_hint="src/main.py",
            ),
            MemoryFact(
                content="missing.py exists",
                confidence=ConfidenceLevel.OBSERVED,
                source="s",
                verification_hint="src/missing.py",
            ),
            MemoryFact(
                content="absolute path",
                confidence=ConfidenceLevel.OBSERVED,
                source="s",
                verification_hint="/etc/passwd",
            ),
        ],
    )
    engine = VerificationEngine(tmp_path)
    verified = await engine.verify_topic(topic)
    assert verified.facts[0].confidence == ConfidenceLevel.OBSERVED
    assert verified.facts[1].confidence == ConfidenceLevel.STALE
    assert verified.facts[2].confidence == ConfidenceLevel.STALE


async def test_recall_verify_does_not_persist_staleness(manager):
    result = await manager.remember(
        "project",
        "Needs verification",
        source="s",
        verification_hint="src/does_not_exist.py",
    )
    topics = await manager.recall("verification", verify=True)
    assert topics[0].facts[0].confidence == ConfidenceLevel.STALE
    stored = await manager.get_topic("project")
    assert stored.facts[0].confidence == ConfidenceLevel.OBSERVED
    assert result.success is True
