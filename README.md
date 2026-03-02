# SchemaDiff

SQL Schema 对比工具 - 比较两个 SQL 文件或目录，生成 Migration 脚本。

## 功能特性

- 🔍 **Schema 对比** - 比较两个数据库 schema 的差异
- 📝 **Migration 生成** - 自动生成 ALTER 语句
- 📁 **目录支持** - 支持目录级别的批量对比
- 🗄️ **多方言支持** - MySQL / PostgreSQL

## 安装

### 从 PyPI 安装 (推荐)

```bash
pip install nevernet-sql-diff
```

### 从源码安装

```bash
git clone https://github.com/nevernet/SchemaDiff.git
cd SchemaDiff
pip install -e .
```

### 开发模式安装

```bash
pip install -e .[dev]
```

## 使用方法

### 命令行

```bash
# 对比两个 SQL 文件
nevernet-sql-diff users_v1.sql users_v2.sql

# 对比两个目录
nevernet-sql-diff backup/20260301 SQL

# 输出到文件
nevernet-sql-diff old.sql new.sql -o migration.sql

# 指定方言
nevernet-sql-diff old.sql new.sql -d postgres
```

### Python 模块

```python
from migration import parse_sql_file, SchemaDiff

# 解析 SQL
source = parse_sql_file("users_v1.sql", "mysql")
target = parse_sql_file("users_v2.sql", "mysql")

# 对比
diff = SchemaDiff(source, target)
changes = diff.compare()

# 生成迁移脚本
migration = diff.generate_migration()
print(migration)
```

## 发布到 PyPI

### 1. 安装发布工具

```bash
pip install build twine
```

### 2. 构建包

```bash
python -m build
```

### 3. 发布到 PyPI

```bash
twine upload dist/*
```

或者使用测试 PyPI:

```bash
twine upload --repository testpypi dist/*
```

### 4. 版本管理

更新版本号请修改:
- `setup.py` 中的 `version`
- Git tag: `git tag v0.1.0 && git push --tags`

## 测试样本

```bash
# 单文件对比
./run.sh SQL/users_v1.sql SQL/users_v2.sql

# 目录对比
./run.sh backup/20260301 SQL

# 输出到文件
./run.sh SQL/users_v1.sql SQL/users_v2.sql -o migration.sql
```

## 支持的 SQL 特性

| 特性 | 状态 |
|------|------|
| CREATE TABLE | ✅ |
| ADD COLUMN | ✅ |
| DROP COLUMN | ✅ |
| ALTER COLUMN | ✅ |
| PRIMARY KEY | ✅ |
| FOREIGN KEY | ✅ |
| UNIQUE INDEX | ✅ |
| DEFAULT VALUE | ✅ |
| AUTO_INCREMENT | ✅ |
| COMMENT | ✅ |

## 技术栈

- Python 3.8+
- sqlglot (SQL 解析)

## 许可证

MIT
