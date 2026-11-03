# Framework integrations

Install the real framework SDKs with:

```bash
pip install -e ".[integrations]"
# or, for the dedicated integration job only:
uv sync --all-extras --frozen
```

These modules are imported lazily and are not required by core Memograph.
CrewAI pulls in `chromadb`, whose current advisories have no patched release;
see [SECURITY.md](https://github.com/knarayanareddy/Memograph/blob/main/SECURITY.md).
Core CI jobs use narrow extras and do not install this dependency.

## LangChain

`LangChainMemory` implements LangChain's `BaseChatMessageHistory` and persists
messages as Memograph facts. A dedicated background event-loop thread keeps
`aiosqlite` operations on one loop.

```python
from langchain_core.messages import HumanMessage, AIMessage
from memograph.integrations import LangChainMemory

with LangChainMemory(base_path=".memograph", session_id="chat_1") as memory:
    memory.add_messages([HumanMessage(content="hello"), AIMessage(content="hi")])
    print(memory.messages)
```

## CrewAI

`CrewAIMemoryBackend` implements CrewAI's storage-backend protocol. Records are
stored in a dedicated SQLite table, mirrored into Memograph topic views, and
optionally indexed in the safe JSON vector store. `CrewAITaskOutputAdapter`
stores `TaskOutput` objects as facts.

```python
from crewai.memory import MemoryRecord
from memograph.integrations import CrewAIMemoryBackend

with CrewAIMemoryBackend(base_path=".memograph") as backend:
    backend.save([
        MemoryRecord(
            id="r1",
            content="Uses FastAPI",
            scope="/project",
            categories=["stack"],
            embedding=[1.0, 0.0],
        )
    ])
    print(backend.search([1.0, 0.0], limit=5))
```

## AutoGen

`AutoGenMemory` consumes `autogen_agentchat.messages` objects directly.

```python
from autogen_agentchat.messages import TextMessage
from memograph.integrations import AutoGenMemory

memory = AutoGenMemory.from_path(".memograph")
async with memory:
    await memory.remember_message(TextMessage(content="Uses FastAPI", source="user"))
    context = await memory.context_for("FastAPI")
    print(context.text)
```

## CI

The `integration` pytest marker selects tests that import these real SDKs.
`.github/workflows/ci.yml` installs `uv.lock` with all extras and runs
`pytest -m integration` in a dedicated job. See [Spec status](SPEC_STATUS.md).
