---
name: nl2sql-db-exec
description: >
  Use this skill to execute SQL queries against the NL2SQL project database (sql_skills_test @ sql_ip:sql_port)
  and get formatted results back. This is the database interaction layer for the NL2SQL workflow —
  use it whenever you need to run SQL, explore field values, list tables, or check table schemas.
  Triggers on: SQL执行, 查数据库, 执行SQL, run SQL, db query, explore database, 数据库查询,
  field value lookup, table schema check, 探查字段, NL2SQL database step.
---

# NL2SQL Database Execution Tool

## Overview

This skill provides a consistent interface for executing SQL queries and database exploration
operations against the NL2SQL project database. It wraps the `scripts/db_query.py` script
to give the LLM a simple, reliable way to interact with the database.

## When to Use

- You need to run a SQL query to get data
- You need to explore what values exist in a specific field
- You need to find which table/column contains a specific value
- You need to check a table's schema
- You need to verify that a generated SQL query produces expected results
- Used in conjunction with `nl2sql-explore-field` for the field extraction phase

## Database Info

```
Host: sql_ip:sql_port
Database: sql_skills_test
User: root
Script: .claude\skills\nl2sql-explore-field\scripts\db_query.py
```

## Available Operations

All commands should be run from the project root:

### 1. Execute Arbitrary SQL

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py "<SQL statement>"
```

Returns JSON with `columns` (list of column names) and `rows` (list of result tuples).

**Safety rules for generated SQL:**
- Always add `LIMIT 100` unless the user specifically needs all results
- Never run INSERT/UPDATE/DELETE — this is a read-only tool
- For large tables, add WHERE filters to narrow results
- Use backticks around column names that might be reserved words

**Example:**
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py "SELECT DISTINCT project_name FROM sql_skills.a WHERE credit_evaluation_total_score LIKE '%10%';"
```

### 2. Cross-table Value Search (--find)

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --find "<value>"
```

Searches across all configured tables and columns to find which ones contain the given value.
Returns match count and sample values for each matching table.column.

This is the **primary tool** for resolving which column an unknown entity belongs to.

**Example:**
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --find "安装工程"
```

### 3. Explore Field Value Distribution (--explore)

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --explore <field_name> <table_name>
```

Shows the distinct values and their frequencies for a specific column. Useful when you need
to understand what values a field can take (e.g., confirming that `city_class` contains "1/2线").

**Example:**
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --explore project_name a
```

### 4. List All Tables (--tables)

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --tables
```

Lists all tables in the database with their comments.

### 5. View Table Schema (--schema)

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --schema <table_name>
```

Shows column names, data types, and comments for a specific table.

**Example:**
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --schema a
```

## Interpreting Results

The script returns JSON. Key fields:
- `columns`: array of column names (for SQL queries)
- `rows`: array of result tuples (for SQL queries)
- `matches`: array of matching table.column entries (for --find)
- `value` + `matches`: the searched value and its matches (for --find)

### Handling Empty Results

If a query returns no rows, DON'T immediately assume the data doesn't exist. Consider:
1. Is the LIKE pattern too specific? Try a shorter substring.
2. Are there alternative column names? (e.g., `contract_brand_name` vs `brand_name`)
3. Could the value exist in a different table entirely?
4. Try `--find` with a shorter version of the value to locate it.

### Handling Errors

If the script returns an error:
1. Check SQL syntax — are backticks needed for reserved words?
2. Verify table and column names against `--tables` and `--schema`
3. Check for type mismatches (comparing string to numeric field)

## Integration with nl2sql-explore-field

This skill is designed to be called BY `nl2sql-explore-field` during the field extraction phase.
The typical pattern:

1. `nl2sql-explore-field` identifies candidate entities in the query
2. For each entity, `nl2sql-explore-field` calls `nl2sql-db-exec` with `--find` to resolve it
3. Results are analyzed to determine the final field mapping
4. The generated SQL is validated by calling `nl2sql-db-exec` to run it
