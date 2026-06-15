
---
name: nl2sql-explore-field
description: >
  Use this skill when doing NL2SQL (Natural Language to SQL) field extraction, entity resolution,
  or when you need to figure out which database table and column a value from a user's natural
  language query belongs to. This skill replaces traditional cached dictionary lookups (AC automaton,
  Jieba word lists) with dynamic database exploration. Use this whenever the user asks a data query
  question in Chinese about brands, plazas, cities, formats, contracts, or other business metrics
  that need to be converted to SQL, and you need to resolve which fields the entities map to.
  Triggers on: NL2SQL, 字段抽取, 自然语言转SQL, 查数据, 问数, brand queries, plaza queries,
  entity resolution from natural language.
---

# NL2SQL Field Extraction via Database Exploration

## Overview

This skill handles the field extraction phase of NL2SQL — mapping entities in a natural language
query to specific database columns. Instead of relying on pre-built dictionaries (AC automaton,
Jieba tokenizers, cached JSON files), it uses **dynamic database exploration**: when an entity
is ambiguous, generate SQL to probe the actual database values and confirm the mapping.

## When to Use This Skill

- User asks a natural language question about business data (brands, plazas, contracts, etc.)
- You need to determine which `table.column` a query term maps to
- You're unsure whether a value is a brand name, city name, project name, or format name
- You need to generate the WHERE clause for an NL2SQL query

## Project Paths

| Resource | Path |
|----------|------|
| Project root | `.claude` |
| DB query script | `.claude\skills\nl2sql-explore-field\scripts\db_query.py` |
| Schema knowledge | `.claude\skills\nl2sql-explore-field\schema.md` |

## Workflow

### Step 1: Dynamically Discover Schema (NOT from cache!)

**Do NOT rely on memorized or cached schema.** Always start by probing the actual database:

```bash
# List current tables
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --tables

# Get fresh schema for the target table
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --schema <table_name>
```

Then read `.claude\skills\nl2sql-explore-field\references\schema.md` for:
- Business rules (time expressions, LIKE vs = rules, naming conventions)
- Known enum values reference (verify with `--explore` before use)
- Windows encoding notes

### Step 2: Parse the Query for Candidate Entities

Scan the user's natural language query and identify all entities that might map to database columns.
Think about what each word/phrase could represent:

| Entity Type | Example Values | Where to Look |
|-------------|----------------|---------------|
| 地区/位置 | 滨江区, 上城区 | Columns like `*location*`, `*district*`, `*city*` — use `--find` to locate |
| 项目类型 | EPC工程, 施工总承包 | Columns like `contract_type`, `*type*` — use `--explore` to see values |
| 建设单位 | XX公司, XX有限公司 | Columns like `client_name`, `*company*` |
| 项目名称关键词 | 学校, 医院 | `project_name` (LIKE search) |
| 资质/评分 | 满分, 10分 | Columns like `*score*`, `*qualification*` — use `--find` |
| 是否/标记 | 是, 否 | Columns like `is_*` — use `--explore` to confirm values |

**Key principle: never guess the column name — use `--find` or `--explore` to verify.**


### Step 3: Explore Ambiguous Entities

For each entity you're uncertain about, use the db_query.py script to probe the database:

#### 3a. Cross-table Search (primary method)
Use this when a value could belong to multiple columns:
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --find "<value>"
```
This **dynamically discovers all text columns** across all tables in the current database and returns which ones contain the value.
No hardcoded config — works even when tables/columns are added or renamed.

Example: `python scripts/db_query.py --find "EPC工程"`
Returns matches like: `contract_type in project_bidding_extract (count: 4)`, `contract_type in project_pre_bidding_extract (count: 3)`

#### 3b. Field Value Distribution (when value is ambiguous)
Use this to see what values a field typically contains:
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --explore <field_name> <table_name>
```
Example: `python scripts/db_query.py --explore contract_type project_bidding_extract`
Shows distinct values like `施工总承包 (26)`, `EPC工程 (4)`, confirming which values exist.

#### 3c. Table Schema (when you need field details)
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --schema <table_name>
```
Dynamically reads from `information_schema` — always up to date.

### Step 4: Determine Field Mapping

Based on exploration results, build the field mapping. Follow these rules:

1. **Text content fields** (project_content, qualification_requirement, etc.) → use `LIKE '%keyword%'`
2. **Enum/dimension fields** (contract_type, is_consortium, etc.) → use `= 'value'` (verify value with `--explore` first)
3. **Location fields** (project_location) → use `LIKE '%district%'` since they store full addresses, not short names
4. **If a value appears in multiple tables**, prefer the table that also contains other matched entities (minimize JOINs)
5. **Table/column names discovered via `--find` take precedence** over assumptions

### Step 5: Output Structured Field Extraction

Produce the field mapping. Column names MUST match what `--find` or `--schema` returned:
```json
[
  {
    "entity": "EPC工程",
    "table": "project_bidding_extract",
    "column": "contract_type",
    "operator": "=",
    "value": "EPC工程"
  },
  {
    "entity": "滨江区",
    "table": "project_bidding_extract",
    "column": "project_location",
    "operator": "LIKE",
    "value": "%滨江区%"
  }
]
```

Also generate the WHERE clause:
```sql
project_bidding_extract.contract_type = 'EPC工程'
AND project_bidding_extract.project_location LIKE '%滨江区%'
```

## Important Rules

- **Always dynamically probe — never assume column names.** Run `--schema`, `--find`, or `--explore` before writing SQL.
- All exploration SQL MUST include LIMIT (script handles this automatically)
- Text content fields (project_content, requirements) always use LIKE, never =
- For enum/dimension fields, run `--explore` first to confirm the exact value, then use `=`
- `project_location` uses LIKE because it stores full addresses
- Minimize cross-table exploration — if multiple entities map to the same table, prefer that table
- If `--find` returns no results, try shorter substrings or fuzzy matching
- When the query uses "多少" (how many), the SELECT should use COUNT(*)
- When the query uses "哪些" (which ones), list the specific column values
- **Windows**: use `PYTHONIOENCODING=utf-8 python scripts/db_query.py ...` to avoid encoding issues

## Example Walkthrough

**User query**: "滨江区有哪些EPC工程项目"

1. **Parse entities**: "滨江区" (地区/位置), "EPC工程" (项目类型/合同类型)
2. **Explore "EPC工程"**: `--find "EPC"` → confirms `contract_type` in `project_bidding_extract` has values `EPC工程`
3. **Explore "滨江区"**: `--find "滨江"` → confirms `project_location` in `project_bidding_extract` stores full addresses containing "滨江区"
4. **Choose table**: Both entities map to `project_bidding_extract` → single table query
5. **Output mapping**:
   - `contract_type = 'EPC工程'`
   - `project_location LIKE '%滨江区%'`
6. **Generate query**: `SELECT project_name, client_name, total_investment FROM project_bidding_extract WHERE contract_type = 'EPC工程' AND project_location LIKE '%滨江区%'`
