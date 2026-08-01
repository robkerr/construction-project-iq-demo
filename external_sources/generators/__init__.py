"""External-source synthetic data generators (OneLake virtualization demo).

These generators produce data for three *external* systems that are brought into
Microsoft Fabric OneLake via mirroring (BigQuery, SQL Server) and shortcuts (S3):

    workorders  -> Google BigQuery  (mirrored)   : work-order management
    timeclock   -> on-prem SQL Server (mirrored)  : time clock / labor
    permits     -> Amazon S3 Parquet (shortcut)   : government permits & inspections

Every row references the real seed-42 keys emitted by ``data_gen/generate.py``
(project_id, wbs_id, supplier_id, equipment_tag) so the external sources fuse
cleanly with the existing Fabric model. Project Falcon (PRJ-001) and the hero
transformer (ET-1001) appear in all three sources.
"""
