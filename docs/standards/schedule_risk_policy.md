# Schedule-Risk Classification & Escalation Policy
**Owner:** Contoso E&C Project Controls · **Doc type:** standard

Contoso E&C classifies project schedule risk using a blended signal that combines NON-SAP
schedule data (Primavera P6) with SAP cost and procurement data. A single governed foundation
is required because no individual system sees the whole picture.

## Risk bands (Schedule Risk Score, 0-100)
- **Green (0-25):** on or ahead of baseline; positive critical-path float; no late long-lead POs.
- **Amber (26-60):** forecast slip present; tightening or slightly negative float; a late
  long-lead PO or a modest forecast overrun.
- **Red (61-100):** material forecast slip; negative critical-path float; a late long-lead PO
  from a High-risk supplier; and/or significant forecast overrun.

## Contributing signals (all must be considered)
| Signal | Source | System |
|---|---|---|
| Forecast slip (days past baseline finish) | Primavera schedule | non-SAP |
| Minimum total float (negative = behind on critical path) | Primavera schedule | non-SAP |
| Critical-path activities forecast to slip | Primavera schedule | non-SAP |
| Approved engineering changes with schedule impact | Engineering-change log | non-SAP |
| Late long-lead purchase orders | SAP Materials Management | SAP |
| Forecast overrun & cost-to-complete exposure | SAP Finance | SAP |
| Supplier risk rating / external disruption signal | SAP vendor master / external | SAP/ext |

## Escalation
- **Red** projects are escalated to the Project Director within 48 hours with a mitigation plan.
- Any **approved** engineering change adding >= 10 days to a critical-path activity triggers an
  immediate change-notice and a schedule re-forecast.
- A late long-lead PO from a **High-risk** supplier requires a supplier recovery plan.
