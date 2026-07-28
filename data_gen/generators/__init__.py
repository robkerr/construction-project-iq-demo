"""Synthetic project-controls data generators, executed in dependency order.

Each table is tagged by origin system (SAP vs non-SAP vs external) so the unification
story is literal, not implied. Order matters: later generators depend on earlier frames.
"""
from . import (
    suppliers,
    projects,
    wbs,
    schedule,
    cost,
    procurement,
    engineering_change,
    bid_evaluation,
    external,
)

PIPELINE = [
    ("suppliers", suppliers),              # SAP vendor master
    ("projects", projects),                # non-SAP project master
    ("wbs", wbs),                          # non-SAP WBS
    ("schedule", schedule),                # non-SAP Primavera activities
    ("cost", cost),                        # SAP finance cost snapshots
    ("procurement", procurement),          # SAP purchase orders
    ("engineering_change", engineering_change),  # non-SAP EC log
    ("bid_evaluation", bid_evaluation),    # SAP sourcing RFQ/bids + non-SAP technical eval
    ("external", external),                # external disruption signals
]

__all__ = ["PIPELINE"]
