# Commercial Bid Evaluation (CBE) Standard
**Owner:** Contoso E&C Procurement / Supply Chain · **Doc type:** standard

A Commercial Bid Evaluation compares the **technically-qualified** bids on a like-for-like basis and
recommends the **lowest evaluated cost**, not simply the lowest quoted price. It works from the
commercial terms & pricing extracted from each supplier's bid document for the tagged equipment.

## Evaluated price (normalization)
```
Evaluated Price = Quoted Price
               + Recommended Spares
               + Freight
               + Technical-deviation loading      (each carried-forward TBE deviation)
               + Commercial-terms deviation loading (deviations to the standard T&Cs)
               + Schedule loading                  (each week delivery lands past Required-On-Site)
               + Advance-payment financing cost    (cost of any advance payment above the 10% norm)
               + Short-warranty loading            (warranty shorter than the 18-month standard)
```

The loadings put every bid on the same commercial footing: a cheap quote with technical deviations,
a long delivery, a large advance payment, or a short warranty is normalized to what it would truly
cost the project.

## Recommendation
- Rank technically-qualified bids by **Evaluated Price**, ascending.
- **Rank 1 → Recommended award.** **Rank 2 → Alternate.** Remaining qualified bids → Not Recommended.
- Disqualified (Non-Compliant) bids are **excluded from the ranking** even if their quoted price is
  the lowest received.

## Rules
- Always report BOTH the lowest *quoted* price and the recommended *evaluated* price, and explain the
  gap (deviations, schedule, terms).
- Cite the delivery week vs Required-On-Site date when a schedule loading is applied.
- Extract commercial terms (price, spares, freight, delivery, payment terms, warranty, Incoterms)
  from the supplier bid documents; never invent a term that is not in the bid.
