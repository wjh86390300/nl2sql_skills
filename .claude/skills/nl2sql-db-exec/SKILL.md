---
name: nl2sql-db-exec
description: >
使用此 `skill` 执行 NL2SQL 项目数据库（sql_skills_test @ sql_ip:sql_port）中的 SQL 查询, 并获取格式化结果。该 `skill` 是 NL2SQL 工作流中的数据库交互层, 当需要执行 SQL、查询字段值、查看数据表、检查表结构时均应使用此 `skill`. 

触发场景:
SQL执行、查数据库、执行SQL、运行SQL、数据库查询、字段值查询、表结构检查、字段探查、数据库探索、NL2SQL数据库步骤。
-----------------------------

# NL2SQL 数据库执行工具

## 概述

该 `skill` 为 NL2SQL 项目数据库提供统一的数据库访问接口。

底层封装了 `scripts/db_query.py` 脚本，使大模型能够以简单、稳定且可控的方式与数据库交互。

支持：

* SQL 查询执行
* 表结构查看
* 字段值探查
* 跨表字段搜索
* SQL 结果验证

该 `skill` 是 NL2SQL 工作流中的数据库访问层。

---

## 使用场景

以下情况应调用本 `skill` ：

* 需要执行 SQL 获取数据
* 需要查看某个字段有哪些取值
* 需要确定某个值属于哪个表或字段
* 需要查看表结构
* 需要验证生成的 SQL 是否正确
* 在字段识别阶段配合 `nl2sql-explore-field` 使用

---

## 数据库信息

```text
Host: sql_ip:sql_port
Database: sql_skills_test
User: root

Script:
cd .claude\skills\nl2sql-explore-field\scripts\db_query.py
```

---

# 支持的操作

所有命令均在项目根目录执行。

---

## 1. 执行 SQL 查询

```bash
cd .claude\skills\nl2sql-explore-field

python scripts/db_query.py "<SQL语句>"
```

返回 JSON：

```json
{
  "columns": [],
  "rows": []
}
```

其中：

* columns：列名列表
* rows：查询结果列表

### SQL生成规范

生成 SQL 时必须遵循：

* 默认添加 `LIMIT 100`
* 禁止执行 INSERT
* 禁止执行 UPDATE
* 禁止执行 DELETE
* 大表查询必须增加 WHERE 条件
* 保留字字段名使用反引号包裹

### 示例

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py "SELECT DISTINCT project_name FROM sql_skills.project_pre_bidding WHERE credit_evaluation_total_score LIKE '%10%';"
```

---

## 2. 跨表字段搜索（--find）

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --find "<value>"
```

作用：

在所有已配置的数据表和字段中搜索指定值。

返回：

* 命中的表
* 命中的字段
* 命中数量
* 示例数据

这是确定实体归属字段的首选工具。

### 示例

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --find "安装工程"
```

适用场景：

用户问题：

```text
安装工程相关项目有哪些？
```

模型无法确定：

```text
安装工程
```

属于哪个字段。

此时应优先调用：

```bash
--find
```

进行定位。

---

## 3. 字段值分布探查（--explore）

```bash
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --explore <field_name> <table_name>
```

作用：

统计指定字段的所有不同取值及出现频次。

适用于：

* 了解字段枚举值
* 确认字段实际存储内容
* 验证用户查询条件

### 示例

```bash
python scripts/db_query.py --explore project_name project_pre_bidding
```

返回示例：

```text
项目A   152
项目B   97
项目C   63
...
```

---

## 4. 查看所有数据表（--tables）

```bash
python scripts/db_query.py --tables
```

作用：

列出数据库中的所有数据表及表注释。

适用于：

* 数据库探索
* NL2SQL表定位
* 新业务接入

---

## 5. 查看表结构（--schema）

```bash
python scripts/db_query.py --schema <table_name>
```

作用：

查看指定表的：

* 字段名
* 数据类型
* 字段注释

### 示例

```bash
python scripts/db_query.py --schema project_pre_bidding
```

返回示例：

```text
project_name     varchar    项目名称
client_name      varchar    招标人名称
budget_amount    decimal    预算金额
...
```

---

# 结果解析

## SQL 查询结果

返回格式：

```json
{
  "columns": [...],
  "rows": [...]
}
```

字段说明：

| 字段      | 说明   |
| ------- | ---- |
| columns | 返回列名 |
| rows    | 查询结果 |

---

## --find 查询结果

返回格式：

```json
{
  "value": "安装工程",
  "matches": [...]
}
```

字段说明：

| 字段      | 说明   |
| ------- | ---- |
| value   | 搜索值  |
| matches | 匹配结果 |

---

# 空结果处理策略

如果 SQL 返回空结果，不应立即认为数据不存在。

应按以下顺序排查：

1. LIKE 条件是否过于严格
2. 是否存在同义字段

例如：

```text
brand_name
contract_brand_name
supplier_name
```

3. 是否查询错了数据表
4. 使用：

```bash
--find
```

搜索更短关键词重新定位

例如：

```text
中国建筑股份有限公司
```

改为：

```text
中国建筑
```

重新搜索。

---

# 异常处理策略

如果执行失败：

## 1. SQL语法检查

确认：

* SQL语法正确
* 保留字已加反引号

---

## 2. 表字段检查

优先执行：

```bash
--tables
```

和：

```bash
--schema
```

确认表名和字段名是否正确。

---

## 3. 类型检查

重点检查：

```sql
text = numeric
varchar = bigint
```

等类型不匹配问题。

例如：

```sql
budget_amount = '100'
```

可能需要：

```sql
CAST(budget_amount AS DECIMAL)
```

---

# 与 nl2sql-explore-field 的协作关系

本 `skill` 主要作为 `nl2sql-explore-field` 的数据库执行层。

典型调用流程：

1. `nl2sql-explore-field` 用于识别查询中的候选实体
2. 对于每个实体，`nl2sql-explore-field`都会调用带有`--find`参数的`nl2sql-db-exec`来解析它
3. 对结果进行分析，以确定最终的野外填图
4. 通过调用`nl2sql-db-exec`来运行生成的SQL，以对其进行验证
