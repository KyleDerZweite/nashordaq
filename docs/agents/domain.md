# Domain docs

This repo uses a single-context domain documentation layout.

## Before exploring

Read root `GLOSSARY.md` for domain vocabulary.
Read relevant decisions in `docs/adr/`.

If these files do not exist, proceed silently.
Domain-modeling creates them when terms or decisions are resolved.

Keep architecture, security, pricing formulas, and product behavior
in the canonical documents named by `AGENTS.md`.
Reference those documents instead of duplicating their details.

## Layout

- `GLOSSARY.md`: shared domain vocabulary.
- `docs/adr/`: architecture decision records.

## Vocabulary

Use glossary terms in issues, proposals, hypotheses, and test names.
Use the same term consistently.

If a needed concept is absent, reconsider whether it belongs to the
project's vocabulary. Record real gaps for domain-modeling.

## Decision conflicts

Explicitly identify proposals that contradict an existing ADR.
Name the ADR and explain why its decision should be reconsidered.
