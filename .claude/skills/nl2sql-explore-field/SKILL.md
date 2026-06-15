---
name: nl2sql-explore-field
description: >
  当进行 NL2SQL(自然语言转SQL)字段抽取、实体解析，或需要确定用户自然语言查询中的某个值应映射到哪个数据库表和列时使用此 `skills` 。此 `skills` 用动态数据库探查替代传统缓存字典(AC 自动机、Jieba 分词词表).
  当用户用中文提出关于业务指标的数据查询问题，需要转换为 SQL，
  且你需要解析实体对应的字段时，使用此 `skills` 。
  触发词：NL2SQL, 字段抽取, 自然语言转SQL, 查数据, 问数, 实体解析。
---

# NL2SQL 字段抽取 — 数据库探查驱动

## 概述

此 `skills` 处理 NL2SQL 的字段抽取阶段 — 将自然语言查询中的实体映射到具体的数据库列。
不依赖预建字典，而是采用**动态数据库探查**：当实体存在歧义时，自动生成 SQL 探查实际数据库值来确认映射关系。

## 使用场景

- 用户提出关于业务数据的自然语言问题
- 需要确定某个查询词映射到哪个 `table.column`
- 不确定一个值是品牌名、城市名、项目名还是业态名等等业务数据
- 需要为 NL2SQL 查询生成 WHERE 子句

## 项目路径

| 资源 | 路径 |
|------|------|
| 项目根目录 | `.claude` |
| 数据库查询脚本 | `.claude\skills\nl2sql-explore-field\scripts\db_query.py` |
| Schema 知识库 | `.claude\skills\nl2sql-explore-field\references\schema.md` |

## 工作流

### 步骤 1：动态发现 Schema(禁止使用缓存！)

**不要依赖记忆或缓存的 schema。** 每次查询前必须探查实际数据库：

```bash
# 列出当前库所有表
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --tables

# 获取目标表的最新结构
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --schema <表名>
```

然后阅读 `.claude\skills\nl2sql-explore-field\references\schema.md` 获取：
- 业务规则(时间表达式、LIKE vs = 规则、命名约定)
- 已知枚举值参考(使用前需通过 `--explore` 验证)
- Windows 编码注意事项

### 步骤 2：解析查询中的候选实体(下面是示例, 不同的数据库有不同的数据)

扫描用户的自然语言查询，识别所有可能映射到数据库列的实体。
思考每个词/短语可能代表什么：

| 实体类型 | 示例值 | 查找方向 |
|---------|--------|---------|
| 地区/位置 | 滨江区, 上城区 | 包含 `*location*`、`*district*`、`*city*` 的列 — 用 `--find` 定位 |
| 项目类型 | EPC工程, 施工总承包 | 包含 `contract_type`、`*type*` 的列 — 用 `--explore` 查看取值 |
| 建设单位 | XX公司, XX有限公司 | 包含 `client_name`、`*company*` 的列 |
| 项目名称关键词 | 学校, 医院 | `project_name`(使用 LIKE) |
| 资质/评分 | 满分, 10分 | 包含 `*score*`、`*qualification*` 的列 — 用 `--find` 定位 |
| 是否/标记 | 是, 否 | 包含 `is_*` 的列 — 用 `--explore` 确认具体值 |

**核心原则：永远不要猜测列名 — 用 `--find` 或 `--explore` 验证。**

### 步骤 3：探查歧义实体

对于每个不确定的实体，使用 `db_query.py` 脚本探查数据库：

#### 3a. 跨表搜索(首选方法)
当某个值可能属于多个列时使用：
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --find "<value>"
```
此命令**动态发现当前数据库所有表中的所有文本列**，并返回哪些列包含该值。
无需硬编码配置 — 即使表或列被新增或重命名也能正常工作。

示例：`python scripts/db_query.py --find "EPC工程"`
返回匹配如：`contract_type in project_bidding_extract (count: 4)`, `contract_type in project_pre_bidding_extract (count: 3)`

#### 3b. 字段值分布探查(值存在歧义时)
查看某个字段通常包含哪些值：
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --explore <field_name> <table_name>
```
示例：`python scripts/db_query.py --explore contract_type project_bidding_extract`
展示不重复值如 `施工总承包 (26)`, `EPC工程 (4)`，以此确认存在哪些值。

#### 3c. 表结构查看(需要了解字段详情时)
```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --schema <table_name>
```
从 `information_schema` 动态读取 — 始终是最新的。

### 步骤 4：确定字段映射

基于探查结果构建字段映射。遵循以下规则：

1. **文本内容字段**(project_content, qualification_requirement 等)→ 使用 `LIKE '%keyword%'`
2. **枚举/维度字段**(contract_type, is_consortium 等)→ 使用 `= 'value'`(先用 `--explore` 验证值)
3. **地区字段**(project_location)→ 使用 `LIKE '%区%'`，因为存储的是完整地址而非常短地名
4. **如果某个值出现在多个表中**，优先选择包含其他已匹配实体的表(减少 JOIN)
5. **通过 `--find` 发现的表/列名优先**于假设

### 步骤 5：输出结构化字段抽取

输出字段映射。列名必须与 `--find` 或 `--schema` 返回的一致：
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

同时生成 WHERE 子句：
```sql
project_bidding_extract.contract_type = 'EPC工程'
AND project_bidding_extract.project_location LIKE '%滨江区%'
```

## 重要规则

- **始终动态探查 — 永远不要假设列名。** 写 SQL 之前先运行 `--schema`、`--find` 或 `--explore`。
- 所有探查 SQL 必须包含 LIMIT(脚本自动处理)
- 文本内容字段(project_content、资质要求等)始终使用 LIKE，禁止使用 `=`
- 对于枚举/维度字段，先运行 `--explore` 确认确切值，然后使用 `=`
- `project_location` 使用 LIKE，因为它存储的是完整地址
- 尽量减少跨表探查 — 如果多个实体可以映射到同一张表，优先使用该表
- 如果 `--find` 返回空结果，尝试更短的子串或模糊匹配
- 查询中使用"多少"时，SELECT 应使用 COUNT(*)
- 查询中使用"哪些"时，列出具体列值
- **Windows**：使用 `PYTHONIOENCODING=utf-8 python scripts/db_query.py ...` 避免编码问题

## 示例演练

**用户查询**："滨江区有哪些EPC工程项目"

1. **解析实体**："滨江区"(地区/位置)、"EPC工程"(项目类型/合同类型)
2. **探查 "EPC工程"**：`--find "EPC"` → 确认 `contract_type` 在 `project_bidding_extract` 中存在值 `EPC工程`
3. **探查 "滨江区"**：`--find "滨江"` → 确认 `project_location` 在 `project_bidding_extract` 中存储包含"滨江区"的完整地址
4. **选择表**：两个实体都映射到 `project_bidding_extract` → 单表查询
5. **输出映射**：
   - `contract_type = 'EPC工程'`
   - `project_location LIKE '%滨江区%'`
6. **生成查询**：`SELECT project_name, client_name, total_investment FROM project_bidding_extract WHERE contract_type = 'EPC工程' AND project_location LIKE '%滨江区%'`
