/* ============================================================
   Fabric Mirroring prep - STEP 3: Verify CDC & permissions
   Database : EmployeeTimeTracking
   Run each query and confirm the expected results noted in comments.
   ============================================================ */
USE [EmployeeTimeTracking];
GO

-- (a) Database-level CDC flag. Expect is_cdc_enabled = 1.
SELECT name, is_cdc_enabled
FROM sys.databases
WHERE name = DB_NAME();

-- (b) Per-table CDC status. Expect one row per mirrored table, is_tracked_by_cdc = 1.
SELECT s.name AS [schema], t.name AS [table], t.is_tracked_by_cdc
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = N'timeclock'
ORDER BY t.name;

-- (c) CDC capture instances. Expect one per table, supports_net_changes = 1.
SELECT ct.capture_instance,
       source_schema = OBJECT_SCHEMA_NAME(ct.source_object_id),
       source_table  = OBJECT_NAME(ct.source_object_id),
       ct.supports_net_changes
FROM cdc.change_tables ct
ORDER BY ct.capture_instance;

-- (d) CDC Agent jobs. Expect a capture job and a cleanup job for this database.
EXEC sys.sp_cdc_help_jobs;

-- (e) SQL Server Agent must be running (required for CDC).
SELECT servicename, status_desc
FROM sys.dm_server_services
WHERE servicename LIKE N'SQL Server Agent%';

-- (f) Fabric user permissions. Expect CONNECT + SELECT granted to fabric_user.
SELECT dp.name AS db_user, dp.type_desc,
       perm.permission_name, perm.state_desc
FROM sys.database_permissions perm
JOIN sys.database_principals dp ON dp.principal_id = perm.grantee_principal_id
WHERE dp.name = N'fabric_user'
ORDER BY perm.permission_name;
GO
