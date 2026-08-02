/* ============================================================
   Fabric Mirroring prep - STEP 1: Enable Change Data Capture (CDC)
   Database : EmployeeTimeTracking
   Schema   : timeclock
   ------------------------------------------------------------
   SQL Server 2016-2022 uses CDC for Fabric Mirroring.
   Run this as a SYSADMIN (e.g., sa). Enabling CDC up front means the Fabric
   login itself does NOT need sysadmin - see mirroring_02_security.sql.
   REQUIREMENT: SQL Server Agent must be RUNNING (CDC capture/cleanup jobs run
   under Agent). Set Agent to Automatic startup.
   Idempotent: safe to re-run.
   ============================================================ */
USE [EmployeeTimeTracking];
GO

-- 0) SQL Server Agent must be running for CDC.
IF NOT EXISTS (
    SELECT 1 FROM sys.dm_server_services
    WHERE servicename LIKE N'SQL Server Agent%' AND status_desc = N'Running')
    PRINT 'WARNING: SQL Server Agent is not running. Start it (Automatic startup recommended) before mirroring.';
GO

-- 1) Enable CDC at the database level.
IF (SELECT is_cdc_enabled FROM sys.databases WHERE name = DB_NAME()) = 0
BEGIN
    EXEC sys.sp_cdc_enable_db;
    PRINT 'CDC enabled at database level.';
END
ELSE
    PRINT 'CDC already enabled at database level.';
GO

-- 2) Enable CDC on each mirrored table.
--    @role_name = NULL -> access to change data is gated only by SELECT on the
--    table, so the read-only fabric_user (granted SELECT in step 2) can read it.
--    @supports_net_changes = 1 requires a primary key (all timeclock tables have one).
DECLARE @schema SYSNAME = N'timeclock';
DECLARE @tables TABLE (name SYSNAME);
INSERT INTO @tables (name) VALUES (N'employee'),(N'crew'),(N'cost_code'),(N'timesheet'),(N'time_entry'),(N'labor_charge');

DECLARE @t SYSNAME;
DECLARE tcur CURSOR LOCAL FAST_FORWARD FOR SELECT name FROM @tables;
OPEN tcur;
FETCH NEXT FROM tcur INTO @t;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM sys.tables tt
        JOIN sys.schemas ss ON ss.schema_id = tt.schema_id
        WHERE ss.name = @schema AND tt.name = @t AND tt.is_tracked_by_cdc = 1)
    BEGIN
        EXEC sys.sp_cdc_enable_table
             @source_schema        = @schema,
             @source_name          = @t,
             @role_name            = NULL,
             @supports_net_changes = 1;
        PRINT 'CDC enabled on ' + @schema + '.' + @t;
    END
    ELSE
        PRINT 'CDC already enabled on ' + @schema + '.' + @t;
    FETCH NEXT FROM tcur INTO @t;
END
CLOSE tcur;
DEALLOCATE tcur;
GO

PRINT 'STEP 1 complete: CDC enabled. Next run mirroring_02_security.sql.';
GO
