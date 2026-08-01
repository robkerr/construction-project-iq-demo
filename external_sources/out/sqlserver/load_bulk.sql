-- Bulk-load the CSV extracts into the [timeclock] tables.
-- Adjust @dir to the folder where you copied the CSV files on the SQL Server host.
-- CSVs have a header row (FIRSTROW = 2) and are UTF-8, comma-delimited.

DECLARE @dir NVARCHAR(400) = 'C:\\timeclock_csv\\';  -- <-- EDIT THIS PATH

BULK INSERT timeclock.employee
FROM '' + @dir + 'employee.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');
GO

BULK INSERT timeclock.crew
FROM '' + @dir + 'crew.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');
GO

BULK INSERT timeclock.cost_code
FROM '' + @dir + 'cost_code.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');
GO

BULK INSERT timeclock.timesheet
FROM '' + @dir + 'timesheet.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');
GO

BULK INSERT timeclock.time_entry
FROM '' + @dir + 'time_entry.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');
GO

BULK INSERT timeclock.labor_charge
FROM '' + @dir + 'labor_charge.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');
GO

-- NOTE: BULK INSERT requires a string literal for FROM. If the paths above
-- error, use this dynamic-SQL pattern per table instead:
--
-- DECLARE @sql NVARCHAR(MAX) = N'BULK INSERT timeclock.employee FROM ''' + @dir +
--   'employee.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''0x0a'', CODEPAGE=''65001'');';
-- EXEC sp_executesql @sql;