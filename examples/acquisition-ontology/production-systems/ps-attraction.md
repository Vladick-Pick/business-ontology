---
id: ps-attraction
type: production-system
status: accepted
source: example-acquisition-source
owner: acquisition-lead
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  business: acquisition
links:
  part-of:
    - acquisition
  produces:
    - qualified-lead
  measured-by:
    - lead-quality
  governed-by:
    - d-handoff-quality
---

# Attraction production system

## Purpose
Turn demand signals into qualified leads.

## Inputs
Market demand signals and contact records.

## Outputs
Qualified leads.
