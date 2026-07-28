# Commercial Bid Evaluation — Output Template
**Owner:** Contoso E&C Procurement · **Doc type:** spec

Use this structure when producing a CBE for the technically-qualified bids.

```
COMMERCIAL BID EVALUATION
RFQ:               <rfq_id>  ·  Tag: <equipment_tag>  ·  Category: <material_category>

Commercial comparison (technically-qualified bids only):
| Supplier | Quoted | Spares | Freight | Delivery (wk) | Payment | Warranty | Incoterms | Loadings | Evaluated |

Recommendation:
  Award:      <supplier> — Evaluated <$>, Quoted <$>  (Rank 1, technically <status>)
  Alternate:  <supplier> — Evaluated <$>
  Note:       Lowest quoted bid was <$ supplier>, DISQUALIFIED (<reason>) / or higher evaluated cost.
```

Rules: rank qualified bids by Evaluated Price; always contrast lowest quoted vs recommended evaluated.
