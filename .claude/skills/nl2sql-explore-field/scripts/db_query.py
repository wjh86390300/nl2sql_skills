#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NL2SQL 数据库查询工具脚本
用法: python db_query.py "<SQL语句>"
      python db_query.py --explore "<字段名>" "<表名>"
      python db_query.py --tables
      python db_query.py --schema "<表名>"
"""
import sys
import os
import json
import pymysql

# Windows: force UTF-8 stdout so Chinese characters don't garble
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.isfile(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key, value = key.strip(), value.strip()
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value

_load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("NL2SQL_DB_HOST", ""),
    "port": int(os.environ.get("NL2SQL_DB_PORT", "")),
    "user": os.environ.get("NL2SQL_DB_USER", ""),
    "password": os.environ["NL2SQL_DB_PASSWORD"],
    "database": os.environ.get("NL2SQL_DB_NAME", "sql_skills_test"),
    "charset": "utf8mb4",
    "connect_timeout": 10,
}

def get_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def execute_sql(sql: str, auto_limit: int = 100) -> dict:
    """执行 SQL 并返回结果。对 SELECT 语句自动追加 LIMIT（如未指定）。"""
    sql_upper = sql.strip().upper()
    # 仅对 SELECT 语句且无 LIMIT 子句时自动追加
    if sql_upper.startswith("SELECT") and "LIMIT" not in sql_upper:
        # 去掉末尾分号再追加 LIMIT
        sql = sql.rstrip().rstrip(";") + f" LIMIT {auto_limit}"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        cursor.close()
        return {"columns": columns, "rows": list(result), "row_count": len(result)}
    finally:
        conn.close()


def explore_field(field_name: str, table_name: str, limit: int = 20) -> dict:
    """
    探查表中某个字段的取值分布
    返回该字段的 DISTINCT 值 + 出现次数
    """
    sql = f"""
    SELECT `{field_name}`, COUNT(*) as cnt 
    FROM `{table_name}`
    WHERE `{field_name}` IS NOT NULL AND `{field_name}` != ''
    GROUP BY `{field_name}`
    ORDER BY cnt DESC
    LIMIT {limit}
    """
    return execute_sql(sql)


def _get_searchable_columns(max_columns: int = 200) -> list:
    """
    动态发现当前数据库中所有可搜索的文本列。
    从 information_schema 实时读取，无需维护硬编码配置。
    max_columns: 最多返回的列数，防止大库扫描过久
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sql = f"""
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND DATA_TYPE IN ('varchar', 'char', 'text', 'mediumtext', 'longtext', 'tinytext')
          AND COLUMN_NAME NOT IN (
              'detail_url', 'attachment_dir', 'attachment_url',
              'bidding_announcement_url', 'bidding_document_url',
              'document_code', 'project_code', 'code',
              'created_at', 'updated_at', 'register_date', 'bid_open_time',
              'bid_deadline', 'pre_publicity_date', 'id'
          )
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        LIMIT {max_columns}
        """
        cursor.execute(sql, (DB_CONFIG["database"],))
        columns = []
        for row in cursor.fetchall():
            table, column, dtype = row[0], row[1], row[2]
            columns.append((table, column))
        cursor.close()
        return columns
    finally:
        conn.close()


def explore_value(value: str, limit: int = 10, max_scan: int = 100, max_results: int = 30) -> dict:
    """
    跨表探查某个值存在于哪些表的哪些字段中（动态发现列，不依赖硬编码配置）
    limit:      每个匹配列返回的样例数（同时也是 DISTINCT 查询的 LIMIT）
    max_scan:   最多扫描的列数，防止大库扫描过久
    max_results: 最多返回的匹配结果数
    """
    search_columns = _get_searchable_columns()
    # 截断扫描列数，优先扫描常用名称列
    if len(search_columns) > max_scan:
        search_columns = search_columns[:max_scan]

    results = []
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for table, column in search_columns:
            if len(results) >= max_results:
                break
            try:
                sql = f"SELECT COUNT(*) as cnt FROM `{table}` WHERE `{column}` LIKE %s LIMIT 1"
                cursor.execute(sql, (f"%{value}%",))

                row = cursor.fetchone()
                if row and row[0] > 0:
                    sample_sql = f"SELECT DISTINCT `{column}` FROM `{table}` WHERE `{column}` LIKE %s LIMIT {limit}"
                    cursor.execute(sample_sql, (f"%{value}%",))
                    samples = [r[0] for r in cursor.fetchall()]

                    results.append({
                        "table": table,
                        "column": column,
                        "match_count": row[0],
                        "samples": samples[:5],
                    })
            except Exception:
                continue
        cursor.close()
    finally:
        conn.close()

    return {"value": value, "matches": results}


def list_tables() -> list:
    """列出所有可用的表"""
    sql = f"""
    SELECT TABLE_NAME, TABLE_COMMENT
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = '{DB_CONFIG["database"]}'
    ORDER BY TABLE_NAME
    """
    return execute_sql(sql)


def get_table_schema(table_name: str) -> dict:
    """获取表结构"""
    sql = f"""
    SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = '{DB_CONFIG["database"]}' AND TABLE_NAME = %s
    ORDER BY ORDINAL_POSITION
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (table_name,))
        columns = [{"name": r[0], "type": r[1], "comment": r[2]} for r in cursor.fetchall()]
        cursor.close()
        return {"table": table_name, "columns": columns}
    finally:
        conn.close()


def print_result(result):
    """格式化输出结果"""
    if isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif isinstance(result, list):
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(result)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print('  python db_query.py "<SQL>"           — 执行任意SQL')
        print('  python db_query.py --explore <字段> <表> — 探查字段值分布')
        print('  python db_query.py --find "<值>"      — 跨表查找值属于哪个字段')
        print('  python db_query.py --tables           — 列出所有表')
        print('  python db_query.py --schema <表名>     — 查看表结构')
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--explore":
        if len(sys.argv) < 4:
            print("用法: python db_query.py --explore <字段名> <表名>")
            sys.exit(1)
        result = explore_field(sys.argv[2], sys.argv[3])
    elif cmd == "--find":
        if len(sys.argv) < 3:
            print("用法: python db_query.py --find <值>")
            sys.exit(1)
        result = explore_value(sys.argv[2])
    elif cmd == "--tables":
        result = list_tables()
    elif cmd == "--schema":
        if len(sys.argv) < 3:
            print("用法: python db_query.py --schema <表名>")
            sys.exit(1)
        result = get_table_schema(sys.argv[2])
    else:
        # 直接执行 SQL
        result = execute_sql(cmd)

    print_result(result)
