# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for docprep.

## What is an ADR?

An ADR records a significant architectural decision along with its context and consequences. ADRs help new contributors understand _why_ things are built the way they are, without having to read through issue threads or ask the original authors.

## When to Write an ADR

Write an ADR when a decision:

- Is non-obvious to someone reading the code for the first time
- Constrains future design choices (closing off alternatives)
- Was debated and has reasonable alternatives that were rejected
- Would be costly to reverse

## ADR Format

Each ADR follows the template in [template.md](template.md): Status, Date, Context, Decision, and Consequences. Keep them concise and jargon-free.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-identity-model.md) | Identity Model | Accepted |
| [0002](0002-adapter-not-parser.md) | Adapter-not-Parser Philosophy | Accepted |
| [0003](0003-chunking-strategy.md) | Chunking Strategy | Accepted |
| [0004](0004-plugin-registry.md) | Plugin Registry | Accepted |
| [0005](0005-diff-then-sync.md) | Diff-then-Sync Pipeline | Accepted |
| [0006](0006-export-contract.md) | Export Contract (VectorRecordV1) | Accepted |
