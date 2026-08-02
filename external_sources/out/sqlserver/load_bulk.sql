-- Bulk-load the CSV extracts into the [timeclock] tables.
-- Requires SQL Server 2017+ (FORMAT = 'CSV').
-- 1) Copy the six timeclock/*.csv files to a folder the SQL Server service
--    account can read, then edit @dir below (keep the trailing backslash).
-- 2) The CSVs are UTF-8 with a header row (FIRSTROW = 2) and Unix (LF) line
--    endings. If your files have Windows (CRLF) endings, change @row to '0x0d0a'.

SET NOCOUNT ON;
DECLARE @dir NVARCHAR(400) = N'C:\timeclock_csv\';  -- <-- EDIT THIS PATH
DECLARE @row NVARCHAR(10)  = N'0x0a';                 -- LF; use '0x0d0a' for CRLF files
DECLARE @sql NVARCHAR(MAX);

SET @sql = N'BULK INSERT timeclock.employee FROM ''' + @dir + N'employee.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''' + @row + N''', TABLOCK, CODEPAGE=''65001'');';
EXEC sys.sp_executesql @sql;

SET @sql = N'BULK INSERT timeclock.crew FROM ''' + @dir + N'crew.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''' + @row + N''', TABLOCK, CODEPAGE=''65001'');';
EXEC sys.sp_executesql @sql;

SET @sql = N'BULK INSERT timeclock.cost_code FROM ''' + @dir + N'cost_code.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''' + @row + N''', TABLOCK, CODEPAGE=''65001'');';
EXEC sys.sp_executesql @sql;

SET @sql = N'BULK INSERT timeclock.timesheet FROM ''' + @dir + N'timesheet.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''' + @row + N''', TABLOCK, CODEPAGE=''65001'');';
EXEC sys.sp_executesql @sql;

SET @sql = N'BULK INSERT timeclock.time_entry FROM ''' + @dir + N'time_entry.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''' + @row + N''', TABLOCK, CODEPAGE=''65001'');';
EXEC sys.sp_executesql @sql;

SET @sql = N'BULK INSERT timeclock.labor_charge FROM ''' + @dir + N'labor_charge.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''' + @row + N''', TABLOCK, CODEPAGE=''65001'');';
EXEC sys.sp_executesql @sql;

PRINT 'Time clock load complete.';