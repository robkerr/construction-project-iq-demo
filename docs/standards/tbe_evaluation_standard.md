# Technical Bid Evaluation (TBE) Standard
**Owner:** Contoso E&C Engineering & Procurement · **Doc type:** standard

A Technical Bid Evaluation compares each supplier's technical proposal against the project
**technical datasheet (RFQ requirements)** for a tagged equipment item and determines which bids
are technically acceptable *before* any commercial comparison. The pilot covers three material
categories — **Heat Exchanger**, **Centrifugal Pump**, and **Electrical Equipment** — and is
designed so new categories can be added with minimal configuration (a new requirement set only).

## Compliance categories (per requirement)
- **Compliant** — the offer meets the specified requirement. Scoring factor **1.0**.
- **Deviation** — the offer differs but may be acceptable after normalization. Scoring factor **0.6**;
  every deviation is carried into the Commercial Bid Evaluation as a price loading.
- **Exception** — the requirement is not met or not addressed. Scoring factor **0.0**.

## Technical score
`Technical Score (0-100) = 100 x SUM(weight x factor) / SUM(weight)` across all requirements, where
`weight` reflects the engineering importance of the requirement (mandatory requirements carry the
highest weights).

## Qualification (the gate to commercial evaluation)
A bid is **technically qualified** only if BOTH hold:
1. **No mandatory requirement is an Exception.** Any Exception on a *mandatory* requirement (e.g. a
   missing design-code compliance or type-test certificate) makes the bid **Non-Compliant** and it is
   **disqualified regardless of price**.
2. **Technical Score ≥ 70.**

TBE status resolves to: **Compliant** (no deviations), **Compliant with Deviations** (qualified, one
or more deviations to normalize), or **Non-Compliant** (disqualified).

## Rules
- Never advance a Non-Compliant bid to commercial comparison on the basis of a low price.
- Name the specific unmet requirement (and whether it was mandatory) when disqualifying a bid.
- Every requirement must be evaluated for every bidder; "not addressed" counts as an Exception.
