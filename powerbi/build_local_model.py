#!/usr/bin/env python3
"""
build_local_model.py — populate the *local, self-contained* EPCDemo PBIP semantic
model (Import mode) from the generated synthetic CSVs in ``out/csv``.

Why this exists
---------------
``fabric/semantic-model/build_semantic_model.py`` builds the **Direct Lake** model
that lives in the Fabric workspace (it reads Lakehouse tables over OneLake and only
works when connected to Fabric). For local dashboard authoring in Power BI Desktop
we want a model that opens and refreshes **offline**, so this script re-uses the
exact same schema (COLS / MEASURES / RELATIONSHIPS — imported from that file so we
never drift) but emits **Import-mode M partitions** that read the local CSV files.

The single source of truth for the folder that holds the CSVs is the ``DataFolder``
M parameter (see ``expressions.tmdl``). It defaults to this repo's ``out/csv``. If
you move the repo or open a different checkout, change that one value in Desktop
(Transform data -> Manage parameters) or edit ``expressions.tmdl``.

Run:  python powerbi/build_local_model.py
Then reload EPCDemo.pbip in Power BI Desktop and Refresh.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

TAB = "\t"

REPO = Path(__file__).resolve().parent.parent
SM_DEF = REPO / "powerbi" / "EPCDemo.SemanticModel" / "definition"
CSV_DIR = REPO / "out" / "csv"

# ---- import COLS / MEASURES / RELATIONSHIPS from the Direct Lake builder (DRY) ----
_src = REPO / "fabric" / "semantic-model" / "build_semantic_model.py"
_spec = importlib.util.spec_from_file_location("dl_builder", _src)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
COLS = _mod.COLS
MEASURES = _mod.MEASURES
RELATIONSHIPS = _mod.RELATIONSHIPS

# TMDL dataType -> Power Query type used in Table.TransformColumnTypes
PQ_TYPE = {
    "string": "type text",
    "int64": "Int64.Type",
    "double": "type number",
    "dateTime": "type datetime",
    "boolean": "type logical",
}


def q(name: str) -> str:
    """Quote a TMDL identifier if it contains spaces or special chars."""
    if any(c in name for c in " .'=:()-"):
        return "'" + name.replace("'", "''") + "'"
    return name


def measure_tmdl(m: dict) -> list[str]:
    out: list[str] = []
    for d in m["desc"].split("\n"):
        out.append(f"{TAB}/// {d}")
    if "lines" in m:
        out.append(f"{TAB}measure {q(m['name'])} = ```")
        for ln in m["lines"]:
            out.append(f"{TAB}{TAB}{TAB}{ln}")
        out.append(f"{TAB}{TAB}{TAB}```")
    else:
        out.append(f"{TAB}measure {q(m['name'])} = {m['dax']}")
    if m.get("fmt"):
        out.append(f"{TAB}{TAB}formatString: {m['fmt']}")
    out.append("")
    return out


def m_partition(tname: str) -> list[str]:
    """Import-mode Power Query partition that reads out/csv/<tname>.csv."""
    transforms = []
    for (cname, dtype, _scol, _hidden, _sby) in COLS[tname]:
        transforms.append(f'{{"{cname}", {PQ_TYPE[dtype]}}}')
    types_list = ", ".join(transforms)
    q6 = TAB * 6  # indentation for M body lines inside the fenced block
    body = [
        f"{TAB}partition {q(tname)} = m",
        f"{TAB}{TAB}mode: import",
        f"{TAB}{TAB}source = ```",
        f'{q6}let',
        f'{q6}{TAB}Source = Csv.Document(File.Contents(DataFolder & "{tname}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        f"{q6}{TAB}Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f"{q6}{TAB}Typed = Table.TransformColumnTypes(Promoted, {{{types_list}}})",
        f"{q6}in",
        f"{q6}{TAB}Typed",
        f"{q6}```",
    ]
    return body


def table_tmdl(tname: str) -> str:
    out = [f"table {q(tname)}", ""]
    for m in MEASURES.get(tname, []):
        out += measure_tmdl(m)
    for (cname, dtype, scol, hidden, sby) in COLS[tname]:
        out.append(f"{TAB}column {q(cname)}")
        out.append(f"{TAB}{TAB}dataType: {dtype}")
        if hidden:
            out.append(f"{TAB}{TAB}isHidden")
        if sby:
            out.append(f"{TAB}{TAB}summarizeBy: {sby}")
        out.append(f"{TAB}{TAB}sourceColumn: {scol}")
        out.append("")
    out += m_partition(tname)
    out.append("")
    return "\n".join(out)


def relationships_tmdl() -> str:
    out: list[str] = []
    for (rname, ft, fc, tt, tc) in RELATIONSHIPS:
        out.append(f"relationship {rname}")
        out.append(f"{TAB}fromColumn: {q(ft)}.{q(fc)}")
        out.append(f"{TAB}toColumn: {q(tt)}.{q(tc)}")
        out.append("")
    return "\n".join(out)


def expressions_tmdl() -> str:
    # trailing backslash so `DataFolder & "file.csv"` resolves correctly
    folder = str(CSV_DIR) + "\\"
    folder_m = folder.replace('"', '""')
    return "\n".join([
        "/// Folder that contains the generated synthetic CSVs (out/csv). Change this one",
        "/// value if you move the repo or open a different checkout.",
        f'expression DataFolder = "{folder_m}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
        "",
    ])


def model_tmdl() -> str:
    out = [
        "model Model",
        f"{TAB}culture: en-US",
        f"{TAB}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{TAB}sourceQueryCulture: en-US",
        f"{TAB}valueFilterBehavior: independent",
        f"{TAB}dataAccessOptions",
        f"{TAB}{TAB}legacyRedirects",
        f"{TAB}{TAB}returnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 1",
        "",
        'annotation PBI_ProTooling = ["DevMode"]',
        "",
        "ref cultureInfo en-US",
        "",
    ]
    for tname in COLS:
        out.append(f"ref table {q(tname)}")
    out.append("")
    return "\n".join(out)


def main() -> None:
    if not CSV_DIR.exists():
        raise SystemExit(f"CSV data not found at {CSV_DIR}. Run generate.py first.")

    tables_dir = SM_DEF / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    (SM_DEF / "model.tmdl").write_text(model_tmdl(), encoding="utf-8")
    (SM_DEF / "expressions.tmdl").write_text(expressions_tmdl(), encoding="utf-8")
    (SM_DEF / "relationships.tmdl").write_text(relationships_tmdl(), encoding="utf-8")
    for tname in COLS:
        (tables_dir / f"{tname}.tmdl").write_text(table_tmdl(tname), encoding="utf-8")

    n_meas = sum(len(v) for v in MEASURES.values())
    print(f"Wrote model.tmdl, expressions.tmdl, relationships.tmdl")
    print(f"Wrote {len(COLS)} table TMDL files -> {tables_dir}")
    print(f"  tables: {', '.join(COLS)}")
    print(f"  measures: {n_meas}   relationships: {len(RELATIONSHIPS)}")
    print(f"  DataFolder -> {CSV_DIR}\\")


if __name__ == "__main__":
    main()
