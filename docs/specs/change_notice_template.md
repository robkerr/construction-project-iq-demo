# Change-Notice Template
**Owner:** Contoso E&C Project Controls · **Doc type:** spec

Use this format when drafting a change-notice for a schedule- or cost-impacting event.

```
CHANGE NOTICE
Project:            <project name> (<project_id>)
Raised by:          <role>            Date: <yyyy-mm-dd>
Trigger:            <EC id / PO id / activity id>
Discipline / WBS:   <discipline> / <wbs_id>

Description:
  <what changed and why, 2-4 sentences>

Schedule impact:    <+N days>  on critical-path activity <activity_id>
Cost impact:        <$ forecast overrun / cost-to-complete exposure>
Supply-chain impact:<late long-lead PO <po_id> from <supplier>, revised +N days>

Recommended action: <mitigation>  Owner: <name>  Need-by: <yyyy-mm-dd>
Approval:           <name / status>
```

Rules: cite the driving EC and PO ids; quote schedule impact in days and cost impact in dollars;
always name the affected critical-path activity.
