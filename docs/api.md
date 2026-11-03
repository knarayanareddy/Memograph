# Python API reference

Generated from source docstrings with mkdocstrings.

## High-level client

::: memograph.MemoGraph
    options:
      show_root_heading: true
      show_source: false
      members:
        - remember
        - recall
        - forget
        - update
        - build_context
        - status
        - dream_now
        - get_context_injection
        - start_session
        - end_session
        - archive_turn
        - grep_transcripts
        - recent_signals
        - prune
        - reconcile

## Core manager

::: memograph.MemoryManager
    options:
      show_root_heading: true
      show_source: false
      members:
        - initialize
        - close
        - remember
        - recall
        - forget
        - update
        - build_context
        - status
        - dream_now
        - reconcile

## REST API factory

::: memograph.api.app.create_app
    options:
      show_root_heading: true
      show_source: false

::: memograph.api.settings.APISettings
    options:
      show_root_heading: true
      show_source: false

::: memograph.api.auth.APIKeyAuth
    options:
      show_root_heading: true
      show_source: false

::: memograph.api.events.EventBroker
    options:
      show_root_heading: true
      show_source: false

::: memograph.api.rate_limit.RateLimiter
    options:
      show_root_heading: true
      show_source: false

## Framework integrations

::: memograph.integrations.langchain.LangChainMemory
    options:
      show_root_heading: true
      show_source: false

::: memograph.integrations.crewai.CrewAIMemoryBackend
    options:
      show_root_heading: true
      show_source: false

::: memograph.integrations.autogen.AutoGenMemory
    options:
      show_root_heading: true
      show_source: false
