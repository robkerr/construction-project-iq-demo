# Technical Bid Evaluation — Output Template
**Owner:** Contoso E&C Engineering · **Doc type:** spec

Use this structure when producing a TBE for a tagged equipment RFQ.

```
TECHNICAL BID EVALUATION
RFQ:               <rfq_id>  ·  Tag: <equipment_tag>  ·  Category: <material_category>
Project:           <project name> (<project_id>)      ·  Required-On-Site: <yyyy-mm-dd>

Compliance matrix (per bidder):
| Requirement | Required value | Mandatory | <Supplier A> | <Supplier B> | ... |
|-------------|----------------|-----------|--------------|--------------|-----|
| ...         | ...            | Y/N       | Compliant    | Exception    | ... |

Roll-up (per bidder):
| Supplier | Technical Score | Deviations | Exceptions | TBE Status | Qualified? |

Recommendation:
  Technically qualified: <suppliers>.  Disqualified: <supplier> — <mandatory requirement not met>.
```

Rules: gate on mandatory Exceptions first; quote the Technical Score; name each disqualifying
requirement.
