# SchemaDiff 计划

## 项目目标
实现 SQL 文件 Schema Diff + 生成 Migration 脚本

## 技术栈
- Python
- sqlglot

## 功能模块

### 1. 数据模型 (schema_models.py)
- `Column` - 列定义
- `Index` - 索引定义
- `ForeignKey` - 外键定义
- `Table` - 表定义
- `DatabaseSchema` - 数据库模式

### 2. 解析器 (parser.py)
- `parse_sql_file()` - 从文件解析
- `parse_sql_text()` - 从文本解析
- 支持 MySQL 和 PostgreSQL 方言

### 3. 比较器 (comparator.py)
- `SchemaDiff` - Schema 比较
- 生成迁移脚本

## 验收标准
1. ✅ 能解析 CREATE TABLE 语句
2. ✅ 能提取表名、列名、列类型
3. ✅ 支持 MySQL 方言
