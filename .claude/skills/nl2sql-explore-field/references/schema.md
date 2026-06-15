# NL2SQL 数据库 Schema 知识库

> 数据库: sql_skills_test @ sql_ip:sql_port
> ⚠️ **本文件不硬编码表结构** — 表和字段通过 `db_query.py` 从数据库实时探查。

---

## 0. 动态 Schema 发现（替代硬编码）

**禁止依赖本文件的表结构！** 每次查询前运行以下命令获取最新结构：

```bash
# 列出当前库所有表
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --tables

# 查看某表结构
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --schema <表名>

# 跨表探查某个值属于哪个字段（已改为动态发现列）
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --find "<值>"

# 探查某字段的值分布
cd .claude\skills\nl2sql-explore-field && python scripts/db_query.py --explore <字段名> <表名>
```

---

## 1. 已知表概览（仅供参考，随时可能变化）

| 表名 | 说明 | 关键可搜索字段 |
|------|------|---------------|
| `project_bidding_extract` | 公示表 | project_name, client_name, project_location, contract_type, is_consortium |
| `project_pre_bidding_extract` | 预公示表 | project_name, client_name, project_location, project_content, contract_type, is_joint_venture |

---

## 2. 字段搜索规则

- **文本内容字段**（project_content, qualification_requirement 等）→ 使用 `LIKE '%keyword%'`
- **枚举/维度字段**（contract_type, is_consortium 等）→ 先用 `--explore` 确认值，然后 `= 'value'`
- **地区字段** `project_location` 存储完整地址字符串（如"杭州市滨江区，东至…"），使用 `LIKE '%滨江%'` 而非 `=`
- **金额字段**（total_investment 等）→ `decimal` 类型，直接数值比较

---

## 3. 关键枚举值参考

以下枚举值来自历史数据探查，仅作参考。使用前用 `--explore` 确认：

| 字段 | 已知枚举值 |
|------|-----------|
| contract_type | `施工总承包`, `EPC工程总承包` |
| is_consortium | `是`, `否` |
| is_joint_venture | `是`, `否` |

---

## 4. 业务规则

### 时间表达规则
- "xx年开业" → 以开业年份匹配 xx 年
- "xx年之后" → 从 xx年1月1日至当前时间
- "xx年截止目前" → 从 xx年1月1日至当前时间

### 名词解释
- "拓店" = 拓展店铺数量
- "固本培元" = 品牌分类属性
- "联发品牌" = 联合发展品牌(总部联发/大区联发)
- "TOP5品牌" = 排名前五的品牌

---

## 5. Windows 编码注意事项

在 Windows 终端执行 Python 脚本时，**必须**设置环境变量避免中文乱码：

```bash
PYTHONIOENCODING=utf-8 python scripts/db_query.py "<SQL>"
```

`db_query.py` 已内置 `sys.stdout.reconfigure(encoding='utf-8')`，但设置环境变量提供额外保障。
