-- Time Clock schema for on-prem SQL Server (mirrored into Microsoft Fabric).
-- Fabric mirroring requires a primary key on every mirrored table.
-- Run against your target database (e.g., TimeClockDB).

IF SCHEMA_ID('timeclock') IS NULL EXEC('CREATE SCHEMA timeclock');
GO

IF OBJECT_ID('timeclock.employee', 'U') IS NOT NULL DROP TABLE timeclock.employee;
CREATE TABLE timeclock.employee (
    emp_id VARCHAR(12) NOT NULL,
    full_name NVARCHAR(120) NOT NULL,
    craft VARCHAR(40) NULL,
    labor_class VARCHAR(30) NULL,
    region VARCHAR(40) NULL,
    hire_date DATE NULL,
    hourly_rate DECIMAL(9,2) NULL,
    is_active BIT NULL,
    origin_system VARCHAR(30) NULL,
    CONSTRAINT PK_employee PRIMARY KEY (emp_id)
);
GO

IF OBJECT_ID('timeclock.crew', 'U') IS NOT NULL DROP TABLE timeclock.crew;
CREATE TABLE timeclock.crew (
    crew_id VARCHAR(12) NOT NULL,
    crew_name NVARCHAR(80) NOT NULL,
    foreman_emp_id VARCHAR(12) NULL,
    project_id VARCHAR(12) NULL,
    discipline VARCHAR(30) NULL,
    origin_system VARCHAR(30) NULL,
    CONSTRAINT PK_crew PRIMARY KEY (crew_id)
);
GO

IF OBJECT_ID('timeclock.cost_code', 'U') IS NOT NULL DROP TABLE timeclock.cost_code;
CREATE TABLE timeclock.cost_code (
    cost_code_id VARCHAR(16) NOT NULL,
    project_id VARCHAR(12) NULL,
    code VARCHAR(20) NULL,
    description NVARCHAR(120) NULL,
    discipline VARCHAR(30) NULL,
    origin_system VARCHAR(30) NULL,
    CONSTRAINT PK_cost_code PRIMARY KEY (cost_code_id)
);
GO

IF OBJECT_ID('timeclock.timesheet', 'U') IS NOT NULL DROP TABLE timeclock.timesheet;
CREATE TABLE timeclock.timesheet (
    timesheet_id VARCHAR(16) NOT NULL,
    emp_id VARCHAR(12) NULL,
    week_ending DATE NULL,
    project_id VARCHAR(12) NULL,
    status VARCHAR(20) NULL,
    total_hours DECIMAL(6,2) NULL,
    origin_system VARCHAR(30) NULL,
    CONSTRAINT PK_timesheet PRIMARY KEY (timesheet_id)
);
GO

IF OBJECT_ID('timeclock.time_entry', 'U') IS NOT NULL DROP TABLE timeclock.time_entry;
CREATE TABLE timeclock.time_entry (
    entry_id VARCHAR(18) NOT NULL,
    timesheet_id VARCHAR(16) NULL,
    emp_id VARCHAR(12) NULL,
    work_date DATE NULL,
    project_id VARCHAR(12) NULL,
    wbs_id VARCHAR(16) NULL,
    cost_code_id VARCHAR(16) NULL,
    clock_in DATETIME2(0) NULL,
    clock_out DATETIME2(0) NULL,
    hours DECIMAL(5,2) NULL,
    overtime_hours DECIMAL(5,2) NULL,
    origin_system VARCHAR(30) NULL,
    CONSTRAINT PK_time_entry PRIMARY KEY (entry_id)
);
GO

IF OBJECT_ID('timeclock.labor_charge', 'U') IS NOT NULL DROP TABLE timeclock.labor_charge;
CREATE TABLE timeclock.labor_charge (
    charge_id VARCHAR(18) NOT NULL,
    project_id VARCHAR(12) NULL,
    wbs_id VARCHAR(16) NULL,
    cost_code_id VARCHAR(16) NULL,
    week_ending DATE NULL,
    reg_hours DECIMAL(8,2) NULL,
    ot_hours DECIMAL(8,2) NULL,
    amount DECIMAL(12,2) NULL,
    origin_system VARCHAR(30) NULL,
    CONSTRAINT PK_labor_charge PRIMARY KEY (charge_id)
);
GO
