/* ============================================================
   Fabric Mirroring prep - STEP 2: Security for the Fabric login
   Database : EmployeeTimeTracking
   ------------------------------------------------------------
   Because CDC is pre-enabled (STEP 1), the Fabric login needs only the MINIMAL
   privileges documented for SQL Server 2016-2022 mirroring:
       Server level  : CONNECT SQL
       Database level: CONNECT, SELECT
   (No sysadmin / db_owner required once CDC already exists.)
   Run this as a SYSADMIN. Idempotent: safe to re-run.
   ============================================================ */

-- 2a) SERVER LEVEL: allow the existing [fabric_login] login to connect.
USE [master];
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'fabric_login')
BEGIN
    PRINT 'NOTE: server login [fabric_login] not found. Create it first, e.g.:';
    PRINT '  CREATE LOGIN [fabric_login] WITH PASSWORD = ''<strong password>'';';
END
ELSE
BEGIN
    GRANT CONNECT SQL TO [fabric_login];
    PRINT 'Granted CONNECT SQL to [fabric_login].';
END
GO

-- 2b) DATABASE LEVEL: map a database user to the login and grant read access.
USE [EmployeeTimeTracking];
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'fabric_user')
BEGIN
    CREATE USER [fabric_user] FOR LOGIN [fabric_login];
    PRINT 'Created database user [fabric_user] for login [fabric_login].';
END
ELSE
    PRINT 'Database user [fabric_user] already exists.';
GO

-- Database-scoped SELECT covers the timeclock tables AND the cdc.* change tables.
GRANT CONNECT, SELECT TO [fabric_user];
GO

PRINT 'STEP 2 complete: [fabric_login] can connect and read. Next run mirroring_03_verify_cdc.sql.';
GO
