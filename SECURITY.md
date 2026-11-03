# Security policy

## Supported versions

The current `main` branch and the active Arena branch receive fixes. This is an
early-alpha project; do not use it as an authorization boundary.

## Reporting

Please report suspected vulnerabilities privately through GitHub's security
advisory flow for this repository. Include a minimal reproduction, the affected
path, and the impact. Do not include real API keys or private memory files.

## Threat model and mitigations

- **Untrusted transcripts and LLM output** are treated as data. Consolidation
  output is parsed into a strict discriminated union; prompt text uses explicit
  untrusted-data delimiters.
- **Path traversal** is prevented by `validate_topic_id()` and
  `safe_relative_path()` with `Path.resolve().is_relative_to()`.
- **Prompt injection into writes** is limited because model-produced operations
  cannot supply arbitrary keyword arguments, absolute paths, or unverified
  `VERIFIED` confidence.
- **Concurrent consolidation** uses atomic POSIX `flock`, not PID/mtime files.
- **Partial writes** use temporary files plus `os.replace`; SQLite is canonical
  and generated views are reconciled at startup.
- **Unsafe deserialization** is avoided: vectors and metadata use JSON, never
  `pickle`.
- **SQL injection** is avoided: `update_dream_run()` whitelists column names and
  vector metadata filters are evaluated in Python.
- **Secrets** stay in environment variables or `.env`, which is ignored by Git.
  `.env.example` contains only empty values.

## Operator responsibilities

- Protect the `.memograph/` directory and `memograph.db` with filesystem
  permissions; they contain agent memories and transcripts.
- Use a provider API key with least privilege and rotate it if exposed.
- Configure CORS/authentication yourself if you add a network-facing API; no
  REST server is shipped in this version.
