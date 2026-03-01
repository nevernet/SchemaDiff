自己基于 sqlglot（pg基于pglast) 实现「SQL 文件 Schema Diff + 生成 Migration 脚本」的完整详细规划（2026 年版）
你明确要自己写（不依赖 Atlas），我给你一个生产级、可落地的详细规划。重点突出你关心的：

解析依赖顺序（Parsing 时如何处理语句先后）
迁移对象完整清单（分 MVP / 进阶 / 完整）
生成迁移时的依赖执行顺序（UP/DOWN 的拓扑顺序，防止 FK/索引报错）


1. 整体架构（推荐类结构）
Pythonproject/
├── schema_models.py      # 核心模型：DatabaseSchema, Table, Column, Index, FK...
├── parser.py             # sqlglot 解析 → 构建 Schema 对象
├── comparator.py         # SchemaA vs SchemaB → DiffOperations 列表
├── generator.py          # DiffOperations → up.sql + down.sql（分 MySQL / PG）
├── dialects/             # mysql_handler.py, postgres_handler.py
├── utils/                # topo_sort, type_mapping 等
└── main.py               # CLI: python main.py --from server.sql --to local.sql --dialect mysql

2. 详细 5 阶段规划 + Checklist + 预计时间（单人开发）
阶段 1：解析 SQL 文件 ★☆☆☆☆（半天 ~ 1 天）
目标：把两个 SQL 文件（server_dump.sql + local_schema.sql）解析成可比较的结构。
Checklist：

sqlglot.parse(sql_text, read="mysql") 或 read="postgres"（支持多语句）
 过滤只保留 DDL：exp.Create（kind=TABLE/INDEX/VIEW）、exp.Alter、exp.Drop
 处理文件中的多语句、注释、USE DATABASE、SET 语句（跳过或记录）
 支持大文件（>10MB）：用 sqlglot.parse + 迭代器，避免内存爆炸
 异常处理：UnsupportedError → 记录日志，继续解析其他语句

依赖顺序（Parsing 时）：

先收集所有 Create(kind=TABLE) → 构建基础表结构（列、inline PK/Unique）
再处理同一表的所有 Alter / Create Index / table-level Constraint
最后处理 FK（因为 FK 可能跨表引用，必须等所有表都解析完）

输出：两个 DatabaseSchema 对象（server_schema, local_schema）

阶段 2：提取完整 Schema 模型 ★★★☆☆（3~7 天）
核心：自己定义 Python 类，把 AST 转成结构化模型。
推荐核心类（schema_models.py）：
Pythonclass Column:
    name: str
    data_type: str          # 规范化后（如 "bigint", "varchar(255)"）
    nullable: bool
    default: str | None
    auto_increment: bool    # MySQL
    generated: dict         # PG GENERATED ALWAYS AS ...
    comment: str | None

class Index:
    name: str
    columns: list[str]
    unique: bool
    type: str | None        # BTREE, HASH...

class ForeignKey:
    name: str
    columns: list[str]
    ref_table: str
    ref_columns: list[str]
    on_delete: str          # CASCADE, SET NULL...
    on_update: str

class Table:
    name: str
    schema: str | None      # public / dbname
    columns: dict[str, Column]
    indexes: dict[str, Index]
    constraints: dict       # pk, unique, check
    fks: dict[str, ForeignKey]
    engine: str | None      # MySQL only
    charset: str | None
    comment: str | None

class DatabaseSchema:
    tables: dict[str, Table]   # key = "schema.table" or "table"
    views: dict[...]           # 后续扩展
Checklist（遍历 AST）：

Create → Table + ColumnDef → Column（处理 DataType.this、nested 类型如 ENUM）
 ColumnConstraint → NotNull / PrimaryKey / Unique / Reference（inline FK）
 Table-level constraints → exp.PrimaryKey / Unique / Check / ForeignKey
 Create Index / Alter Add Index
 MySQL 特有：ENGINE=, AUTO_INCREMENT, CHARACTER SET
 PG 特有：SERIAL → auto_increment, GENERATED, COLLATE

MySQL vs PG 完整差异映射表：

| 特性 | MySQL 处理 | PostgreSQL 处理 | 统一规范化策略 |
|------|-----------|-----------------|---------------|
| **自增序列** | `AUTO_INCREMENT` | `SERIAL` / `GENERATED ALWAYS AS IDENTITY` | 统一转换为 `auto_increment=True` + `identity=True` |
| **数据类型别名** | `INT`→`integer`, `BOOL`→`tinyint(1)` | `INT`→`integer`, `SERIAL`→`bigint` | 建立类型别名映射表，统一转换后存储 |
| **字符类型** | `VARCHAR(n)`, `TEXT` | `VARCHAR(n)`, `TEXT` | 统一保留，校验长度限制 |
| **时间类型** | `DATETIME`, `TIMESTAMP` | `TIMESTAMP`, `DATETIME` | 统一转为 `TIMESTAMP` |
| **数值类型** | `TINYINT`, `SMALLINT`, `INT`, `BIGINT`, `FLOAT`, `DOUBLE`, `DECIMAL` | `SMALLINT`, `INT`, `BIGINT`, `REAL`, `DOUBLE PRECISION`, `NUMERIC` | 统一使用标准类型名 |
| **JSON 类型** | `JSON` (MySQL 5.7+) | `JSONB` | 统一转为 `JSON` |
| **FK 内联** | `ColumnConstraint(Reference)` | 同上 | 统一解析为 `ForeignKey` 对象 |
| **默认值** | `CURRENT_TIMESTAMP`, `NOW()`, 常量 | `CURRENT_TIMESTAMP`, 常量 | 使用 sqlglot 规范化表达式后再比较 |
| **注释** | `COMMENT 'xxx'` | `COMMENT ON COLUMN/TABLE` | 统一提取到 `comment` 字段 |
| **字符集/排序** | `CHARSET=utf8mb4`, `COLLATE` | `ENCODING`, `COLLATE` | 记录但 diff 时可选对比 |
| **存储引擎** | `ENGINE=InnoDB` | N/A | MySQL 特有，记录在 table 属性 |
| **分区** | `PARTITION BY` | `PARTITION BY` | Level 3 再支持 |
| **表达式索引** | `((col_func(col)))` | `(col_func(col))` | 提取表达式文本进行比较 |
| **条件索引** | `WHERE` 子句 | `WHERE` 子句 | 提取 `where_clause` 字段 |
| **唯一约束** | `UNIQUE KEY` | `UNIQUE CONSTRAINT` | 统一转为 `Index(unique=True)` |
| **主键** | `PRIMARY KEY` | `PRIMARY KEY` | 统一转为 `PrimaryKey` 对象 |
| **检查约束** | `CHECK (expr)` | `CHECK (expr)` | 提取 `check_clause` 字段 |
| **序列** | 无 | `CREATE SEQUENCE` | Level 3 再支持 |
| **视图** | `CREATE VIEW` | `CREATE VIEW` | Level 3 再支持 |
| **触发器** | `CREATE TRIGGER` | `CREATE TRIGGER` | Level 3 再支持 |
| **存储过程** | `CREATE PROCEDURE` | `CREATE PROCEDURE` | Level 3 再支持 |

### 类型兼容性判断矩阵

| 源类型 | 目标类型 | 可直接 ALTER | 需要数据迁移 | 需要警告 |
|--------|---------|-------------|-------------|---------|
| `INT` | `BIGINT` | ✅ | - | - |
| `BIGINT` | `INT` | ❌ | ✅ | ✅ 数据截断风险 |
| `VARCHAR(10)` | `VARCHAR(5)` | ✅ | - | ✅ 数据截断风险 |
| `VARCHAR(10)` | `VARCHAR(20)` | ✅ | - | - |
| `INT` | `VARCHAR` | ❌ | ✅ | ✅ 类型变更 |
| `DATETIME` | `TIMESTAMP` | ✅ | - | - |
| `TEXT` | `VARCHAR(255)` | ❌ | ✅ | ✅ 数据丢失 |
| `CHAR` | `VARCHAR` | ✅ | - | - |
| `JSON` | `TEXT` | ✅ | - | - |

阶段 3：Schema 对比（Diff） ★★★★☆（1~2 周）
输入：server_schema vs local_schema
输出：有序的 DiffOperation 列表（AddTable, DropTable, AlterColumn, AddFK...）
Checklist：

 表级：新增表 / 删除表 / 重命名表（需用户确认）
 列级：AddColumn / DropColumn / AlterColumn（type change, nullable, default）
 索引级：AddIndex / DropIndex / AlterIndex
 约束级：AddPK / DropPK / AddUnique / AddCheck / AddFK / DropFK
 类型兼容性判断（INT→BIGINT 可 ALTER；VARCHAR(10)→VARCHAR(5) 需警告数据丢失）
 默认值表达式对比（用 sqlglot.transpile 规范化后再比）


阶段 4：生成迁移 SQL（最难） ★★★★★（2~4 周 + 持续维护）
核心难点：依赖执行顺序（必须拓扑排序！）
生成迁移时的依赖顺序（UP 脚本标准顺序）：
SQL-- 1. 先 DROP 所有可能阻塞的约束（反向依赖）
DROP FOREIGN KEY ...
DROP INDEX ...
DROP CONSTRAINT ...

-- 2. DROP 表/列（反向拓扑顺序：被引用的表最后 DROP）
DROP TABLE IF EXISTS child_table;   -- 先删子表
DROP TABLE IF EXISTS parent_table;

-- 3. CREATE 新表（无 FK 约束，或只带 inline PK/Unique）
CREATE TABLE new_table (...);

-- 4. ALTER 已存在表（加列、改类型、改默认值）
ALTER TABLE ... ADD COLUMN ...
ALTER TABLE ... MODIFY COLUMN ...

-- 5. CREATE INDEX（包括唯一索引）

-- 6. ADD 约束（最后加 FK，避免循环引用）
ALTER TABLE ... ADD CONSTRAINT fk_xxx FOREIGN KEY ...
DOWN 脚本 = 上面操作的完全逆序 + 逆操作（Add → Drop, Create → Drop 等）
Checklist：

 实现拓扑排序（用 networkx 或自己写 Kahn 算法，表 + FK 建图）
 分 dialect 生成器（mysql_generator.py / postgres_generator.py）
 支持事务包裹（BEGIN; ... COMMIT;）
 生成可回滚 DOWN 文件
 数据迁移提示注释（当列类型缩小、NOT NULL 加默认值时）
 临时表技巧（MySQL 大表改类型常用）


阶段 5：边缘案例 & 长期维护 ★★★★★（持续）
完整迁移对象清单（分层级）：








































### 完整迁移对象清单（分层级）

| 层级 | 支持对象 | MVP必须 | 难度 | 备注 |
|------|---------|--------|------|------|
| **MVP** | Table, Column, Primary Key, Unique Index, Foreign Key | ✅ | ★★ | 覆盖 80% 日常场景 |
| **Level 2** | Check Constraint, Default Value, Column Comment, Table Comment, Non-Unique Index | 推荐 | ★★★ | 增强完整性检查 |
| **Level 3** | View, Trigger, Stored Procedure, Partition Table, Sequence (PG) | 后期 | ★★★★ | 高级特性 |
| **Advanced** | Extension (PG), Materialized View, Engine/Collate (MySQL) | 按需 | ★★★★★ | 特殊场景 |

### MySQL 8.x vs PostgreSQL 16 特别注意

| 特性 | MySQL 8.x | PostgreSQL 16 |
|------|-----------|---------------|
| **生成列** | `GENERATED ALWAYS AS (expr) VIRTUAL/STORED` | 不支持 |
| **JSON 类型** | `JSON` (原生函数支持) | `JSONB` (二进制，更好的性能) |
| **窗口函数** | 支持 | 支持 |
| **默认表达式** | `CURRENT_TIMESTAMP`, `NOW()` | `CURRENT_TIMESTAMP` |
| **新分区语法** | `PARTITION BY RANGE/LIST/HASH` | `PARTITION BY RANGE/LIST/HASH` (PG 16 增强) |
| **IDENTITY 列** | `AUTO_INCREMENT` (传统方式) | `GENERATED ALWAYS AS IDENTITY` (标准) |
| **MERGE 语句** | `MERGE INTO` | `MERGE INTO` (PG 15+) |
| **CTE 递归** | 支持 | 支持 |
| **RETURNING** | 不支持 (MySQL 8.0.20+ 有替代方案) | 支持 |

### 本项目实际需求分析

基于当前 `SQL/` 目录的 SQL 文件结构分析：

| 对象类型 | 出现频率 | 迁移复杂度 | 优先级 |
|---------|---------|-----------|--------|
| Table | 高 | 低 | MVP |
| Column | 高 | 低 | MVP |
| Primary Key | 高 | 低 | MVP |
| Foreign Key | 中 | 中 | MVP |
| Index | 中 | 中 | MVP |
| Unique Constraint | 中 | 低 | Level 2 |
| Comment | 低 | 低 | Level 2 |
| Check Constraint | 极低 | 中 | Level 2 |
| View | 极低 | 高 | Level 3 |
| Trigger | 极低 | 高 | Level 3 |
| Partition | 极低 | 高 | Level 3 |

**建议 MVP 阶段先支持**: Table, Column, Primary Key, Foreign Key, Index (含 Unique)

---

## 4. 技术实现细节

### 4.1 核心数据模型（schema_models.py）

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from collections import OrderedDict

@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    auto_increment: bool = False
    generated: Optional[dict] = None
    comment: Optional[str] = None

@dataclass
class Index:
    name: str
    columns: List[str]
    unique: bool = False
    index_type: Optional[str] = None
    where_clause: Optional[str] = None

@dataclass
class ForeignKey:
    name: str
    columns: List[str]
    ref_table: str
    ref_columns: List[str]
    on_delete: Optional[str] = None
    on_update: Optional[str] = None

@dataclass
class Table:
    name: str
    schema: Optional[str] = None
    columns: OrderedDict[str, Column] = field(default_factory=OrderedDict)
    indexes: Dict[str, Index] = field(default_factory=dict)
    primary_key: Optional[List[str]] = None
    fks: Dict[str, ForeignKey] = field(default_factory=dict)
    engine: Optional[str] = None
    charset: Optional[str] = None
    comment: Optional[str] = None

@dataclass
class DatabaseSchema:
    tables: Dict[str, Table] = field(default_factory=dict)
    views: Dict[str, dict] = field(default_factory=dict)
    
    def get_table_key(self, table: Table) -> str:
        """获取表唯一键，支持 schema.table 格式"""
        if table.schema:
            return f"{table.schema}.{table.name}"
        return table.name
```

### 4.2 解析器核心函数（parser.py）

```python
import sqlglot
from sqlglot import exp

def parse_sql_file(file_path: str, dialect: str = "mysql") -> DatabaseSchema:
    """解析 SQL 文件为 DatabaseSchema"""
    with open(file_path, 'r', encoding='utf-8') as f:
        sql_text = f.read()
    return parse_sql_text(sql_text, dialect)

def parse_sql_text(sql_text: str, dialect: str = "mysql") -> DatabaseSchema:
    """解析 SQL 文本为 DatabaseSchema"""
    schema = DatabaseSchema()
    
    for statement in sqlglot.parse(sql_text, read=dialect):
        if isinstance(statement, exp.Create):
            if isinstance(statement.this, exp.Table):
                table = parse_create_table(statement, dialect)
                schema.tables[schema.get_table_key(table)] = table
        elif isinstance(statement, exp.Alter):
            # 处理 ALTER TABLE 语句
            process_alter_table(statement, schema, dialect)
    
    return schema

def parse_create_table(create: exp.Create, dialect: str) -> Table:
    """解析 CREATE TABLE 语句"""
    table_name = create.this.name
    table = Table(name=table_name)
    
    # 解析列定义
    for col_def in create.find_all(exp.ColumnDef):
        column = parse_column_def(col_def, dialect)
        table.columns[column.name] = column
    
    # 解析表级约束
    for constraint in create.find_all(exp.Constraint):
        process_table_constraint(constraint, table, dialect)
    
    return table

def normalize_data_type(data_type: exp.DataType) -> str:
    """规范化数据类型为标准形式"""
    type_map = {
        'INT': 'INTEGER',
        'BIGINT': 'BIGINT', 
        'TINYINT': 'TINYINT',
        'SMALLINT': 'SMALLINT',
        'MEDIUMINT': 'MEDIUMINT',
        'FLOAT': 'FLOAT',
        'DOUBLE': 'DOUBLE',
        'DECIMAL': 'DECIMAL',
        'CHAR': 'CHAR',
        'VARCHAR': 'VARCHAR',
        'TEXT': 'TEXT',
        'DATETIME': 'TIMESTAMP',
        'TIMESTAMP': 'TIMESTAMP',
        'JSON': 'JSON',
        'BOOL': 'BOOLEAN',
    }
    base_type = data_type.this.upper() if data_type.this else data_type.name.upper()
    normalized = type_map.get(base_type, base_type)
    
    # 处理长度参数
    if data_type.args.get('length'):
        length = data_type.args['length']
        normalized = f"{normalized}({length})"
    
    return normalized
```

### 4.3 比较器核心函数（comparator.py）

```python
from enum import Enum
from typing import List, Tuple

class DiffOperationType(Enum):
    ADD_TABLE = "ADD_TABLE"
    DROP_TABLE = "DROP_TABLE"
    ALTER_TABLE = "ALTER_TABLE"
    ADD_COLUMN = "ADD_COLUMN"
    DROP_COLUMN = "DROP_COLUMN"
    ALTER_COLUMN = "ALTER_COLUMN"
    ADD_INDEX = "ADD_INDEX"
    DROP_INDEX = "DROP_INDEX"
    ADD_FK = "ADD_FK"
    DROP_FK = "DROP_FK"

@dataclass
class DiffOperation:
    op_type: DiffOperationType
    table_name: str
    object_name: Optional[str] = None
    old_value: Optional[any] = None
    new_value: Optional[any] = None
    warnings: List[str] = field(default_factory=list)

def compare_schemas(old_schema: DatabaseSchema, new_schema: DatabaseSchema) -> List[DiffOperation]:
    """对比两个 Schema，返回差异操作列表"""
    diffs = []
    
    old_tables = set(old_schema.tables.keys())
    new_tables = set(new_schema.tables.keys())
    
    # 新增表
    for table_key in new_tables - old_tables:
        diffs.append(DiffOperation(DiffOperationType.ADD_TABLE, table_key))
    
    # 删除表
    for table_key in old_tables - new_tables:
        diffs.append(DiffOperation(DiffOperationType.DROP_TABLE, table_key))
    
    # 共同表的列对比
    for table_key in old_tables & new_tables:
        old_table = old_schema.tables[table_key]
        new_table = new_schema.tables[table_key]
        
        col_diffs = compare_columns(old_table, new_table)
        diffs.extend(col_diffs)
        
        # 索引对比
        idx_diffs = compare_indexes(old_table, new_table)
        diffs.extend(idx_diffs)
        
        # FK 对比
        fk_diffs = compare_fks(old_table, new_table)
        diffs.extend(fk_diffs)
    
    return diffs

def compare_columns(old_table: Table, new_table: Table) -> List[DiffOperation]:
    """对比两个表的列"""
    diffs = []
    old_cols = set(old_table.columns.keys())
    new_cols = set(new_table.columns.keys())
    
    for col_name in new_cols - old_cols:
        diffs.append(DiffOperation(DiffOperationType.ADD_COLUMN, 
                                   old_table.name, col_name,
                                   new_value=new_table.columns[col_name]))
    
    for col_name in old_cols - new_cols:
        diffs.append(DiffOperation(DiffOperationType.DROP_COLUMN,
                                   old_table.name, col_name,
                                   old_value=old_table.columns[col_name]))
    
    for col_name in old_cols & new_cols:
        old_col = old_table.columns[col_name]
        new_col = new_table.columns[col_name]
        
        # 检查类型、nullable、default 变化
        if old_col.data_type != new_col.data_type:
            warning = check_type_compatibility(old_col.data_type, new_col.data_type)
            diffs.append(DiffOperation(DiffOperationType.ALTER_COLUMN,
                                       old_table.name, col_name,
                                       old_value=old_col, new_value=new_col,
                                       warnings=[warning] if warning else []))
    
    return diffs
```

### 4.4 拓扑排序与依赖管理（generator.py）

```python
from typing import List, Dict, Set
import networkx as nx

def topological_sort_tables(tables: List[str], fk_dependencies: Dict[str, Set[str]]) -> List[str]:
    """
    拓扑排序表顺序，确保 FK 依赖正确
    fk_dependencies[child_table] = {parent_table1, parent_table2, ...}
    """
    graph = nx.DiGraph()
    
    # 添加所有表节点
    for table in tables:
        graph.add_node(table)
    
    # 添加 FK 依赖边 (parent -> child, 即父表必须在子表之前创建)
    for child, parents in fk_dependencies.items():
        for parent in parents:
            if parent in tables:  # 只添加存在的表
                graph.add_edge(parent, child)
    
    try:
        return list(nx.topological_sort(graph))
    except nx.NetworkXError:
        # 循环依赖，回退到原始顺序并警告
        return tables

def order_migration_operations(diffs: List[DiffOperation], schema: DatabaseSchema) -> List[DiffOperation]:
    """
    正确排序迁移操作，防止 FK/索引报错
    标准顺序:
    1. DROP CONSTRAINT (FK, Index, Check)
    2. DROP TABLE/COLUMN (反向依赖)
    3. CREATE TABLE (无 FK 或仅 inline PK/Unique)
    4. ALTER TABLE ADD/MODIFY COLUMN
    5. CREATE INDEX
    6. ADD CONSTRAINT (FK 最后)
    """
    DROP_BEFORE_CREATE = [
        DiffOperationType.DROP_FK,
        DiffOperationType.DROP_INDEX,
        DiffOperationType.DROP_COLUMN,
        DiffOperationType.DROP_TABLE,
    ]
    
    CREATE_AFTER_DROP = [
        DiffOperationType.ADD_TABLE,
        DiffOperationType.ADD_COLUMN,
        DiffOperationType.ALTER_COLUMN,
        DiffOperationType.ADD_INDEX,
        DiffOperationType.ADD_FK,
    ]
    
    # 分组
    drop_ops = [d for d in diffs if d.op_type in DROP_BEFORE_CREATE]
    create_ops = [d for d in diffs if d.op_type in CREATE_AFTER_DROP]
    
    # DROP 操作按反向依赖排序（被引用的先删）
    drop_ops.sort(key=lambda x: get_dependency_depth(x.table_name, schema), reverse=True)
    
    # CREATE 操作按依赖深度排序
    create_ops.sort(key=lambda x: get_dependency_depth(x.table_name, schema))
    
    return drop_ops + create_ops

def get_dependency_depth(table_name: str, schema: DatabaseSchema) -> int:
    """计算表的依赖深度（被多少表引用）"""
    depth = 0
    table = schema.tables.get(table_name)
    if not table:
        return 0
    
    for other_table in schema.tables.values():
        for fk in other_table.fks.values():
            if fk.ref_table == table_name:
                depth += 1
                break
    
    return depth
```

### 4.5 SQL 生成器（generator.py）

```python
def generate_migration(diffs: List[DiffOperation], dialect: str = "mysql", 
                       wrap_transaction: bool = True) -> Tuple[str, str]:
    """
    生成迁移 SQL
    返回 (up_sql, down_sql)
    """
    up_statements = []
    down_statements = []
    
    for diff in diffs:
        up_sql, down_sql = generate_single_operation(diff, dialect)
        up_statements.append(up_sql)
        down_statements.append(down_sql)
    
    up = "\n".join(up_statements)
    down = "\n".join(reversed(down_statements))
    
    if wrap_transaction:
        up = f"BEGIN;\n{up}\nCOMMIT;"
        down = f"BEGIN;\n{down}\nCOMMIT;"
    
    return up, down

def generate_single_operation(diff: DiffOperation, dialect: str) -> Tuple[str, str]:
    """生成单个差异操作的 SQL"""
    generators = {
        'mysql': mysql_generate,
        'postgres': postgres_generate,
    }
    
    generator = generators.get(dialect, mysql_generate)
    return generator(diff)

def mysql_generate(diff: DiffOperation) -> Tuple[str, str]:
    """MySQL 特定的 SQL 生成"""
    table = diff.table_name
    
    if diff.op_type == DiffOperationType.ADD_TABLE:
        # ... 实现
        pass
    elif diff.op_type == DiffOperationType.ADD_COLUMN:
        col = diff.new_value
        up = f"ALTER TABLE `{table}` ADD COLUMN `{col.name}` {col.type_definition}"
        down = f"ALTER TABLE `{table}` DROP COLUMN `{col.name}`"
        return up, down
    
    # ... 其他类型
    
    return "-- unsupported", "-- unsupported"
```

---

## 5. CLI 接口设计

```bash
# 基础用法
python main.py diff --from ./SQL --to ./backup/20260301 --dialect mysql

# 指定输出文件
python main.py diff --from ./SQL --to ./backup/20260301 --dialect mysql -o migration.sql

# PostgreSQL
python main.py diff --from ./SQL_PG --to ./backup-pg/20260301 --dialect postgres

# 仅显示差异，不生成文件
python main.py diff --from ./SQL --to ./backup/20260301 --dry-run

# 仅包含指定表
python main.py diff --from ./SQL --to ./backup/20260301 --include "user,order,product"

# 排除指定表
python main.py diff --from ./SQL --to ./backup/20260301 --exclude "log,audit"
```

---

## 6. 项目文件结构

```
db-models/
├── migration/
│   ├── __init__.py
│   ├── schema_models.py      # 核心数据模型
│   ├── parser.py             # SQL 解析器
│   ├── comparator.py         # Schema 对比
│   ├── generator.py          # SQL 生成 + 拓扑排序
│   ├── dialects/
│   │   ├── __init__.py
│   │   ├── mysql_handler.py  # MySQL 特定处理
│   │   └── postgres_handler.py # PostgreSQL 特定处理
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── type_mapping.py   # 类型映射
│   │   └── topo_sort.py      # 拓扑排序工具
│   └── cli.py                # 命令行入口
├── SQL/                       # 当前开发环境 Schema
├── SQL_PG/                    # PostgreSQL Schema
├── backup/                    # 历史备份
├── test-mysql/               # 测试用例
└── test-pg/                  # PostgreSQL 测试用例
```

---

## 7. 单元测试设计

```python
# tests/test_parser.py
def test_parse_simple_create_table():
    sql = "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));"
    schema = parse_sql_text(sql, "mysql")
    
    assert "users" in schema.tables
    assert schema.tables["users"].columns["id"].data_type == "INTEGER"
    assert schema.tables["users"].primary_key == ["id"]

def test_parse_foreign_key():
    sql = """
    CREATE TABLE orders (id INT PRIMARY KEY, user_id INT, 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);
    """
    schema = parse_sql_text(sql, "mysql")
    
    assert "orders" in schema.tables
    fk = schema.tables["orders"].fks.get("user_id")
    assert fk.ref_table == "users"
    assert fk.on_delete == "CASCADE"

# tests/test_comparator.py  
def test_compare_add_column():
    old_schema = parse_sql_text("CREATE TABLE t (id INT);", "mysql")
    new_schema = parse_sql_text("CREATE TABLE t (id INT, name VARCHAR(100));", "mysql")
    
    diffs = compare_schemas(old_schema, new_schema)
    
    assert any(d.op_type == DiffOperationType.ADD_COLUMN and d.object_name == "name" 
               for d in diffs)

# tests/test_topo_sort.py
def test_topo_sort_fk_order():
    tables = ["orders", "users", "products"]
    deps = {"orders": {"users"}, "products": set()}
    
    result = topological_sort_tables(tables, deps)
    
    assert result.index("users") < result.index("orders")
```

---

## 8. 本项目适配说明

### 8.1 当前 SQL 文件结构分析

基于 `SQL/` 目录的实际 SQL 文件，解析器需要处理以下特殊情况：

| 特性 | 示例 | 处理方式 |
|------|------|---------|
| **USE DATABASE** | `USE \`card_user\`;` | 提取为默认 schema |
| **CREATE DATABASE** | `CREATE DATABASE ... \`card_user\`` | 解析并记录数据库名 |
| **MySQL 注释** | `/*!32312 IF NOT EXISTS*/` | sqlglot 自动处理 |
| **SET 语句** | `SET character_set_client = utf8mb4;` | 跳过，不影响 schema |
| **字符集设置** | `CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci` | 提取到 table.charset / table.collate |
| **存储引擎** | `ENGINE=InnoDB` | 提取到 table.engine |
| **自增** | `AUTO_INCREMENT=206` | 提取到 column.auto_increment |
| **表注释** | `COMMENT='名片里面所使用的字段'` | 提取到 table.comment |
| **列注释** | `COMMENT '用户填写的默认值'` | 提取到 column.comment |

### 8.2 需要处理的 SQL 方言特性

```python
# MySQL 特有语法处理
MYSQL_SPECIFIC = {
    # 注释内语法 (sqlglot 已处理)
    '/*!32312 IF NOT EXISTS*/': '条件注释',
    '/*!40101 SET ... */': '版本注释',
    
    # 自动递增
    'AUTO_INCREMENT': '自增主键',
    
    # 存储引擎
    'ENGINE': 'InnoDB/MyISAM',
    
    # 字符集
    'CHARSET': 'utf8mb4/latin1',
    'COLLATE': '排序规则',
    
    # 锁表选项
    'LOCK TABLES': '表锁',
}
```

### 8.3 目录结构适配

本项目的 SQL 文件按数据库名分开存储：

```
SQL/
├── card_activity.sql    # card_activity 库
├── card_admin_user.sql # card_admin_user 库
├── card_banner.sql     # card_banner 库
├── card_course.sql     # card_course 库
├── ...
├── scrm_user.sql       # scrm_user 库
├── zcs_*.sql           # zcs_* 库
```

解析器需要支持两种模式：
1. **单文件模式**: `parse_sql_file('SQL/card_user.sql')` → 解析单个库的 schema
2. **目录模式**: `parse_sql_dir('SQL/')` → 解析整个目录，返回 `{db_name: DatabaseSchema}`

### 8.4 备份目录结构

```
backup/20260301/        # 按日期的备份
├── card_activity.sql
├── card_admin_user.sql
├── ...
└── zcs_*.sql
```

迁移工具需要对比两个目录的差异：
```bash
# 对比两个备份目录
python main.py diff --from ./backup/20260301 --to ./SQL --dialect mysql

# 对比单个文件
python main.py diff --from ./backup/20260301/card_user.sql --to ./SQL/card_user.sql --dialect mysql
```

### 8.5 多数据库迁移策略

由于本项目涉及多个独立的 MySQL 数据库，建议采用以下策略：

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| **单库对比** | 逐个对比每个 .sql 文件 | 开发阶段，快速迭代 |
| **批量对比** | 对比整个 SQL/ 目录 | 发布前完整检查 |
| **选择性对比** | 通过 --include 过滤 | 只关心某些表的变更 |

```bash
# 只对比 card_user 和 card_order 相关
python main.py diff --from ./backup/20260301 --to ./SQL --include "card_user,card_order"

# 排除日志类表
python main.py diff --from ./backup/20260301 --to ./SQL --exclude "log,audit,history"
```

### 8.6 PostgreSQL 支持

当前项目有 `SQL_PG/` 目录包含 PostgreSQL Schema：

```
SQL_PG/
├── scrm_bim.sql
├── scrm_bim_gres.sql
└── scrm_gis.sql
```

PG 解析器需要额外处理：
- **Schema**: `public` / 自定义 schema
- **序列**: `CREATE SEQUENCE`
- **数组类型**: `integer[]`
- **JSONB**: 二进制 JSON
- **EXISTS**: 物化视图

---

## 9. 实现优先级建议

### Phase 1: MVP（1-2 周）

| 任务 | 预计时间 | 验收标准 |
|------|---------|---------|
| 解析 CREATE TABLE 语句 | 2 天 | 能解析表名、列、类型 |
| 解析 PRIMARY KEY | 0.5 天 | 能识别主键列 |
| 解析 INDEX / KEY | 1 天 | 能识别索引 |
| Schema 对比 | 2 天 | 能输出 ADD/DROP TABLE |
| 生成基础 SQL | 2 天 | 生成可执行的 ALTER 语句 |

### Phase 2: 完善（2-3 周）

| 任务 | 预计时间 | 验收标准 |
|------|---------|---------|
| 支持目录批量解析 | 1 天 | 解析 SQL/ 下所有文件 |
| FK 解析与排序 | 2 天 | 正确处理 FK 依赖 |
| Column 完整属性 | 1 天 | nullable, default, comment |
| 类型兼容性警告 | 1 天 | 给出风险提示 |
| DOWN 回滚脚本 | 2 天 | 生成逆向 SQL |

### Phase 3: 进阶（3-4 周）

| 任务 | 预计时间 | 验收标准 |
|------|---------|---------|
| View 支持 | 2 天 | 解析视图定义 |
| Trigger 支持 | 2 天 | 解析触发器 |
| PostgreSQL 支持 | 3 天 | 完整支持 PG 方言 |
| CLI 完善 | 1 天 | 参数校验、帮助信息 |

---

## 10. 风险与限制

### 10.1 已知的解析限制

| 场景 | 当前支持 | 备注 |
|------|---------|------|
| 分区表 | 部分 | Level 3 再支持 |
| 存储过程 | 否 | 需要 Level 3 |
| 触发器 | 部分 | 复杂触发器可能解析失败 |
| 事件调度 | 否 | 暂不支持 |
| 物化视图 | 否 | PG only, Level 3 |

### 10.2 迁移风险提示

⚠️ **生产环境迁移前必读**：

1. **数据备份**: 迁移前务必完整备份
2. **灰度发布**: 先在测试环境验证
3. **锁表风险**: MySQL ALTER 可能锁表，建议使用 `pt-online-schema-change`
4. **数据类型缩小**: VARCHAR(100) → VARCHAR(50) 会截断数据
5. **删除操作**: DROP TABLE / COLUMN 会永久丢失数据
6. **FK 约束**: 删除前确认无循环依赖

### 10.3 推荐的工作流

```bash
# 1. 生成差异
python main.py diff --from ./backup/20260301 --to ./SQL -o migration.sql

# 2. 审查差异（人工确认）
cat migration.sql

# 3. 在测试环境执行
mysql -u root -p test_db < migration.sql

# 4. 验证应用
# ... 测试业务功能 ...

# 5. 生产环境执行（建议低峰期）
mysql -u root -p production_db < migration.sql
```

---

3. 立即可用的 Starter Code（复制即用）
我可以立刻给你：

schema_models.py 完整类定义（50 行）
parser.py 核心解析函数（支持 MySQL/PG）
comparator.py 基础 diff 框架
generator.py + 依赖拓扑排序函数

你现在告诉我：

先要哪个阶段的完整代码？（推荐先拿 Parser + Schema Model）
还是要整个项目 GitHub 模板结构（我可以描述 + 关键文件内容）
要不要包含类型映射表 + 兼容性判断函数？

这个规划已经完全覆盖“解析依赖顺序”和“哪些要迁移”的所有细节。
---

## 4. 补充实现细节

### 4.1 get_dependency_depth 完整实现

```python
def get_dependency_depth(table_name: str, schema: DatabaseSchema) -> int:
    """计算表的依赖深度（被多少表引用）"""
    depth = 0
    table = schema.tables.get(table_name)
    if not table:
        return 0
    
    for other_table in schema.tables.values():
        for fk in other_table.fks.values():
            if fk.ref_table == table_name:
                depth += 1
    
    return depth
```

### 4.2 循环依赖检测与处理

```python
from typing import List, Dict, Set, Tuple
import networkx as nx
from dataclasses import dataclass

@dataclass
class CircularDependency:
    tables: List[str]
    fk_names: List[str]

def detect_circular_dependencies(
    tables: List[str], 
    fk_dependencies: Dict[str, Set[str]]
) -> List[CircularDependency]:
    """
    检测循环依赖
    返回所有循环依赖链
    """
    graph = nx.DiGraph()
    
    for table in tables:
        graph.add_node(table)
    
    for child, parents in fk_dependencies.items():
        for parent in parents:
            if parent in tables:
                graph.add_edge(parent, child)
    
    cycles = list(nx.simple_cycles(graph))
    
    return [CircularDependency(tables=cycle, fk_names=[]) for cycle in cycles]

def resolve_circular_dependencies(
    diffs: List[DiffOperation],
    schema: DatabaseSchema,
    circular_deps: List[CircularDependency]
) -> Tuple[List[DiffOperation], List[DiffOperation]]:
    """
    解决循环依赖问题
    策略：将 FK 约束延迟创建
    
    Returns:
        (main_operations, deferred_fk_operations)
    """
    deferred_fks = []
    main_ops = []
    
    involved_tables = set()
    for cd in circular_deps:
        involved_tables.update(cd.tables)
    
    for diff in diffs:
        if diff.op_type == DiffOperationType.ADD_FK:
            if diff.table_name in involved_tables:
                deferred_fks.append(diff)
                continue
        main_ops.append(diff)
    
    return main_ops, deferred_fks

def generate_circular_dependency_warning(circular_deps: List[CircularDependency]) -> str:
    """生成循环依赖警告信息"""
    warnings = []
    for cd in circular_deps:
        tables_str = " -> ".join(cd.tables + [cd.tables[0]])
        warnings.append(f"检测到循环依赖: {tables_str}")
        warnings.append("  解决方案: FK 约束将在所有表创建后再添加")
    return "\n".join(warnings)
```

### 4.3 重命名检测实现

```python
from typing import List, Optional, Tuple
from dataclasses import dataclass
import difflib

@dataclass
class RenameOperation:
    old_name: str
    new_name: str
    object_type: str
    confidence: float
    similarity_details: dict

class RenameDetector:
    SIMILARITY_THRESHOLD = 0.7
    
    def __init__(self, old_schema: DatabaseSchema, new_schema: DatabaseSchema):
        self.old_schema = old_schema
        self.new_schema = new_schema
    
    def detect_table_renames(self) -> List[RenameOperation]:
        renames = []
        
        dropped_tables = set(self.old_schema.tables.keys()) - set(self.new_schema.tables.keys())
        added_tables = set(self.new_schema.tables.keys()) - set(self.old_schema.tables.keys())
        
        for old_table_name in dropped_tables:
            old_table = self.old_schema.tables[old_table_name]
            
            for new_table_name in added_tables:
                new_table = self.new_schema.tables[new_table_name]
                
                similarity = self._calculate_table_similarity(old_table, new_table)
                
                if similarity['overall'] >= self.SIMILARITY_THRESHOLD:
                    renames.append(RenameOperation(
                        old_name=old_table_name,
                        new_name=new_table_name,
                        object_type='table',
                        confidence=similarity['overall'],
                        similarity_details=similarity
                    ))
        
        return renames
    
    def detect_column_renames(self, table_name: str) -> List[RenameOperation]:
        renames = []
        
        if table_name not in self.old_schema.tables or table_name not in self.new_schema.tables:
            return renames
        
        old_table = self.old_schema.tables[table_name]
        new_table = self.new_schema.tables[table_name]
        
        dropped_cols = set(old_table.columns.keys()) - set(new_table.columns.keys())
        added_cols = set(new_table.columns.keys()) - set(old_table.columns.keys())
        
        for old_col_name in dropped_cols:
            old_col = old_table.columns[old_col_name]
            
            for new_col_name in added_cols:
                new_col = new_table.columns[new_col_name]
                
                similarity = self._calculate_column_similarity(old_col, new_col)
                
                if similarity >= self.SIMILARITY_THRESHOLD:
                    renames.append(RenameOperation(
                        old_name=old_col_name,
                        new_name=new_col_name,
                        object_type='column',
                        confidence=similarity,
                        similarity_details={'table': table_name}
                    ))
        
        return renames
    
    def _calculate_table_similarity(self, table1: Table, table2: Table) -> dict:
        cols1 = set(table1.columns.keys())
        cols2 = set(table2.columns.keys())
        
        col_overlap = len(cols1 & cols2)
        col_total = len(cols1 | cols2)
        col_similarity = col_overlap / col_total if col_total > 0 else 0
        
        type_matches = 0
        type_checks = 0
        for col_name in cols1 & cols2:
            if table1.columns[col_name].data_type == table2.columns[col_name].data_type:
                type_matches += 1
            type_checks += 1
        type_similarity = type_matches / type_checks if type_checks > 0 else 0
        
        name_similarity = difflib.SequenceMatcher(
            None, 
            table1.name.lower(), 
            table2.name.lower()
        ).ratio()
        
        return {
            'column_overlap': col_similarity,
            'type_match': type_similarity,
            'name_similarity': name_similarity,
            'overall': col_similarity * 0.5 + type_similarity * 0.3 + name_similarity * 0.2
        }
    
    def _calculate_column_similarity(self, col1: Column, col2: Column) -> float:
        score = 0.0
        
        if col1.data_type == col2.data_type:
            score += 0.4
        
        if col1.nullable == col2.nullable:
            score += 0.2
        
        if col1.default == col2.default:
            score += 0.2
        
        name_similarity = difflib.SequenceMatcher(
            None, 
            col1.name.lower(), 
            col2.name.lower()
        ).ratio()
        score += name_similarity * 0.2
        
        return score
```

### 4.4 类型兼容性检查

```python
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re

class TypeChangeSafety(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    REQUIRES_MIGRATION = "requires_migration"

@dataclass
class TypeCompatibilityResult:
    safety: TypeChangeSafety
    message: Optional[str] = None
    data_loss_risk: bool = False
    requires_data_migration: bool = False

TYPE_HIERARCHY = {
    'TINYINT': 1,
    'SMALLINT': 2,
    'MEDIUMINT': 3,
    'INT': 4,
    'INTEGER': 4,
    'BIGINT': 5,
}

TYPE_COMPATIBILITY_MATRIX = {
    ('INT', 'BIGINT'): TypeCompatibilityResult(TypeChangeSafety.SAFE),
    ('BIGINT', 'INT'): TypeCompatibilityResult(
        TypeChangeSafety.WARNING, 
        "数据截断风险: BIGINT → INT 可能丢失数据",
        data_loss_risk=True
    ),
    ('INT', 'VARCHAR'): TypeCompatibilityResult(
        TypeChangeSafety.REQUIRES_MIGRATION,
        "类型变更: INT → VARCHAR 需要数据迁移",
        requires_data_migration=True
    ),
    ('VARCHAR', 'TEXT'): TypeCompatibilityResult(TypeChangeSafety.SAFE),
    ('TEXT', 'VARCHAR'): TypeCompatibilityResult(
        TypeChangeSafety.WARNING,
        "数据丢失风险: TEXT → VARCHAR 可能截断数据",
        data_loss_risk=True
    ),
    ('DATETIME', 'TIMESTAMP'): TypeCompatibilityResult(TypeChangeSafety.SAFE),
    ('TIMESTAMP', 'DATETIME'): TypeCompatibilityResult(TypeChangeSafety.SAFE),
    ('CHAR', 'VARCHAR'): TypeCompatibilityResult(TypeChangeSafety.SAFE),
    ('JSON', 'TEXT'): TypeCompatibilityResult(TypeChangeSafety.SAFE),
    ('TEXT', 'JSON'): TypeCompatibilityResult(
        TypeChangeSafety.WARNING,
        "类型变更: TEXT → JSON，请确保数据为有效 JSON 格式"
    ),
}

def extract_base_type(data_type: str) -> str:
    match = re.match(r'^([A-Z]+)', data_type.upper())
    return match.group(1) if match else data_type.upper()

def extract_type_length(data_type: str) -> Optional[int]:
    match = re.search(r'\((\d+)\)', data_type)
    return int(match.group(1)) if match else None

def check_type_compatibility(old_type: str, new_type: str) -> TypeCompatibilityResult:
    old_base = extract_base_type(old_type)
    new_base = extract_base_type(new_type)
    
    if old_base == new_base:
        return check_same_type_compatibility(old_type, new_type, old_base)
    
    key = (old_base, new_base)
    if key in TYPE_COMPATIBILITY_MATRIX:
        return TYPE_COMPATIBILITY_MATRIX[key]
    
    if old_base in TYPE_HIERARCHY and new_base in TYPE_HIERARCHY:
        old_rank = TYPE_HIERARCHY[old_base]
        new_rank = TYPE_HIERARCHY[new_base]
        
        if new_rank > old_rank:
            return TypeCompatibilityResult(TypeChangeSafety.SAFE)
        else:
            return TypeCompatibilityResult(
                TypeChangeSafety.WARNING,
                f"数值类型缩小: {old_base} → {new_base} 可能丢失数据",
                data_loss_risk=True
            )
    
    return TypeCompatibilityResult(
        TypeChangeSafety.DANGEROUS,
        f"未知类型变更: {old_type} → {new_type}，请手动检查"
    )

def check_same_type_compatibility(old_type: str, new_type: str, base_type: str) -> TypeCompatibilityResult:
    old_len = extract_type_length(old_type)
    new_len = extract_type_length(new_type)
    
    if old_len is None and new_len is None:
        return TypeCompatibilityResult(TypeChangeSafety.SAFE)
    
    if old_len is not None and new_len is not None:
        if new_len >= old_len:
            return TypeCompatibilityResult(TypeChangeSafety.SAFE)
        else:
            return TypeCompatibilityResult(
                TypeChangeSafety.WARNING,
                f"长度缩小: {old_type} → {new_type} 可能截断数据",
                data_loss_risk=True
            )
    
    if old_len is None and new_len is not None:
        return TypeCompatibilityResult(
            TypeChangeSafety.WARNING,
            f"添加长度限制: {old_type} → {new_type} 可能截断数据",
            data_loss_risk=True
        )
    
    return TypeCompatibilityResult(TypeChangeSafety.SAFE)

def check_nullable_change(old_nullable: bool, new_nullable: bool) -> TypeCompatibilityResult:
    if old_nullable and not new_nullable:
        return TypeCompatibilityResult(
            TypeChangeSafety.WARNING,
            "添加 NOT NULL 约束，请确保没有 NULL 数据或已设置默认值",
            requires_data_migration=True
        )
    return TypeCompatibilityResult(TypeChangeSafety.SAFE)
```

### 4.5 数据安全检查机制

```python
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum

class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    DESTRUCTIVE = "destructive"

@dataclass
class SafetyCheckResult:
    level: SafetyLevel
    operation: str
    message: str
    suggestion: Optional[str] = None
    requires_backup: bool = False
    requires_confirmation: bool = False

class SafetyChecker:
    DESTRUCTIVE_OPERATIONS = [
        DiffOperationType.DROP_TABLE,
        DiffOperationType.DROP_COLUMN,
    ]
    
    DANGEROUS_OPERATIONS = [
        DiffOperationType.ALTER_COLUMN,
    ]
    
    def __init__(self, safe_mode: bool = True):
        self.safe_mode = safe_mode
        self.results: List[SafetyCheckResult] = []
    
    def check_operation(self, diff: DiffOperation, type_result: Optional[TypeCompatibilityResult] = None) -> SafetyCheckResult:
        if diff.op_type in self.DESTRUCTIVE_OPERATIONS:
            return self._check_destructive_operation(diff)
        
        if diff.op_type in self.DANGEROUS_OPERATIONS:
            return self._check_dangerous_operation(diff, type_result)
        
        if diff.op_type == DiffOperationType.ADD_FK:
            return self._check_fk_addition(diff)
        
        return SafetyCheckResult(
            level=SafetyLevel.SAFE,
            operation=f"{diff.op_type.value} on {diff.table_name}",
            message="操作安全"
        )
    
    def _check_destructive_operation(self, diff: DiffOperation) -> SafetyCheckResult:
        if diff.op_type == DiffOperationType.DROP_TABLE:
            return SafetyCheckResult(
                level=SafetyLevel.DESTRUCTIVE,
                operation=f"DROP TABLE {diff.table_name}",
                message=f"即将删除表 {diff.table_name}，所有数据将丢失",
                suggestion="请确保已备份重要数据",
                requires_backup=True,
                requires_confirmation=True
            )
        
        if diff.op_type == DiffOperationType.DROP_COLUMN:
            return SafetyCheckResult(
                level=SafetyLevel.DESTRUCTIVE,
                operation=f"DROP COLUMN {diff.table_name}.{diff.object_name}",
                message=f"即将删除列 {diff.object_name}，该列所有数据将丢失",
                suggestion="请确保该列数据不再需要或已迁移",
                requires_backup=True,
                requires_confirmation=True
            )
        
        return SafetyCheckResult(
            level=SafetyLevel.WARNING,
            operation=f"{diff.op_type.value}",
            message="需要确认的操作"
        )
    
    def _check_dangerous_operation(self, diff: DiffOperation, type_result: Optional[TypeCompatibilityResult]) -> SafetyCheckResult:
        if type_result and type_result.data_loss_risk:
            return SafetyCheckResult(
                level=SafetyLevel.DANGEROUS,
                operation=f"ALTER COLUMN {diff.table_name}.{diff.object_name}",
                message=type_result.message or "类型变更可能导致数据丢失",
                suggestion="建议先备份数据，并在测试环境验证",
                requires_backup=True,
                requires_confirmation=True
            )
        
        return SafetyCheckResult(
            level=SafetyLevel.WARNING,
            operation=f"ALTER COLUMN {diff.table_name}.{diff.object_name}",
            message="列结构变更",
            requires_confirmation=self.safe_mode
        )
    
    def _check_fk_addition(self, diff: DiffOperation) -> SafetyCheckResult:
        return SafetyCheckResult(
            level=SafetyLevel.WARNING,
            operation=f"ADD FOREIGN KEY on {diff.table_name}",
            message="添加外键约束可能影响现有数据",
            suggestion="请确保引用完整性，避免孤儿数据",
            requires_confirmation=self.safe_mode
        )
    
    def generate_safety_report(self, diffs: List[DiffOperation]) -> str:
        report_lines = ["# 迁移安全检查报告\n"]
        
        destructive = [r for r in self.results if r.level == SafetyLevel.DESTRUCTIVE]
        dangerous = [r for r in self.results if r.level == SafetyLevel.DANGEROUS]
        warnings = [r for r in self.results if r.level == SafetyLevel.WARNING]
        
        if destructive:
            report_lines.append("## ⚠️ 破坏性操作\n")
            for r in destructive:
                report_lines.append(f"- **{r.operation}**: {r.message}")
                if r.suggestion:
                    report_lines.append(f"  - 建议: {r.suggestion}")
            report_lines.append("")
        
        if dangerous:
            report_lines.append("## ⚡ 危险操作\n")
            for r in dangerous:
                report_lines.append(f"- **{r.operation}**: {r.message}")
                if r.suggestion:
                    report_lines.append(f"  - 建议: {r.suggestion}")
            report_lines.append("")
        
        if warnings:
            report_lines.append("## 📋 注意事项\n")
            for r in warnings:
                report_lines.append(f"- {r.operation}: {r.message}")
            report_lines.append("")
        
        if destructive or dangerous:
            report_lines.append("## 🔒 建议操作\n")
            report_lines.append("1. 在执行迁移前备份目标数据库")
            report_lines.append("2. 先在测试环境验证迁移脚本")
            report_lines.append("3. 在低峰期执行迁移")
            report_lines.append("4. 准备回滚方案")
        
        return "\n".join(report_lines)
```

### 4.6 配置文件设计

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import yaml
import json

@dataclass
class MigrationConfig:
    dialect: str = "mysql"
    safe_mode: bool = True
    ignore_tables: List[str] = field(default_factory=list)
    ignore_columns: Dict[str, List[str]] = field(default_factory=dict)
    ignore_indexes: Dict[str, List[str]] = field(default_factory=dict)
    type_aliases: Dict[str, str] = field(default_factory=lambda: {
        'INT': 'INTEGER',
        'BOOL': 'BOOLEAN',
        'CHARACTER VARYING': 'VARCHAR',
    })
    output_dir: str = "migrations"
    use_transactions: bool = True
    add_comments: bool = True
    rename_detection: bool = True
    rename_similarity_threshold: float = 0.7
    
    @classmethod
    def from_yaml(cls, path: str) -> 'MigrationConfig':
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
    
    @classmethod
    def from_json(cls, path: str) -> 'MigrationConfig':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)
    
    def to_yaml(self, path: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.__dict__, f, default_flow_style=False, allow_unicode=True)
    
    def should_ignore_table(self, table_name: str) -> bool:
        return table_name in self.ignore_tables
    
    def should_ignore_column(self, table_name: str, column_name: str) -> bool:
        if table_name in self.ignore_columns:
            return column_name in self.ignore_columns[table_name]
        return False
```

### 4.7 迁移版本管理

```python
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import hashlib
import json

@dataclass
class MigrationFile:
    version: str
    name: str
    up_sql: str
    down_sql: str
    checksum: str
    created_at: datetime = field(default_factory=datetime.now)
    applied: bool = False
    applied_at: Optional[datetime] = None
    
    @property
    def filename(self) -> str:
        return f"V{self.version}__{self.name}.sql"
    
    def calculate_checksum(self) -> str:
        content = f"{self.up_sql}|{self.down_sql}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        return {
            'version': self.version,
            'name': self.name,
            'checksum': self.checksum,
            'created_at': self.created_at.isoformat(),
            'applied': self.applied,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None
        }

class MigrationVersionManager:
    VERSION_FORMAT = "%Y%m%d%H%M%S"
    
    def __init__(self, migrations_dir: str):
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.migrations_dir / "migration_history.json"
        self.migrations: List[MigrationFile] = []
        self._load_history()
    
    def _load_history(self) -> None:
        if self.history_file.exists():
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                for item in history.get('migrations', []):
                    migration = MigrationFile(
                        version=item['version'],
                        name=item['name'],
                        up_sql='',
                        down_sql='',
                        checksum=item['checksum'],
                        created_at=datetime.fromisoformat(item['created_at']),
                        applied=item['applied'],
                        applied_at=datetime.fromisoformat(item['applied_at']) if item.get('applied_at') else None
                    )
                    self.migrations.append(migration)
    
    def _save_history(self) -> None:
        history = {
            'migrations': [m.to_dict() for m in self.migrations]
        }
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    
    def generate_version(self) -> str:
        return datetime.now().strftime(self.VERSION_FORMAT)
    
    def create_migration(self, name: str, up_sql: str, down_sql: str) -> MigrationFile:
        version = self.generate_version()
        migration = MigrationFile(
            version=version,
            name=name,
            up_sql=up_sql,
            down_sql=down_sql,
            checksum=hashlib.sha256(f"{up_sql}|{down_sql}".encode()).hexdigest()[:16]
        )
        
        self._write_migration_file(migration)
        self.migrations.append(migration)
        self._save_history()
        
        return migration
    
    def _write_migration_file(self, migration: MigrationFile) -> None:
        file_path = self.migrations_dir / migration.filename
        
        content = f"""-- Migration: {migration.name}
-- Version: {migration.version}
-- Created: {migration.created_at.isoformat()}
-- Checksum: {migration.checksum}

-- ===== UP =====
{migration.up_sql}

-- ===== DOWN =====
{migration.down_sql}
"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def mark_applied(self, version: str) -> None:
        for migration in self.migrations:
            if migration.version == version:
                migration.applied = True
                migration.applied_at = datetime.now()
                self._save_history()
                break
    
    def get_pending_migrations(self) -> List[MigrationFile]:
        return [m for m in self.migrations if not m.applied]
    
    def get_last_applied(self) -> Optional[MigrationFile]:
        applied = [m for m in self.migrations if m.applied]
        if applied:
            return max(applied, key=lambda m: m.version)
        return None
```

---

## 5. 推荐目录结构

```
migration/
├── core/
│   ├── __init__.py
│   ├── schema_models.py      # 核心数据模型
│   ├── parser.py             # SQL 解析器
│   ├── comparator.py         # Schema 对比器
│   └── generator.py          # 迁移脚本生成器
├── dialects/
│   ├── __init__.py
│   ├── base.py               # 方言基类
│   ├── mysql.py              # MySQL 方言实现
│   └── postgres.py           # PostgreSQL 方言实现
├── comparator/
│   ├── __init__.py
│   ├── rename_detector.py    # 重命名检测
│   └── type_checker.py       # 类型兼容性检查
├── utils/
│   ├── __init__.py
│   ├── topo_sort.py          # 拓扑排序
│   ├── circular_dependency.py # 循环依赖处理
│   └── type_mapper.py        # 类型映射工具
├── safety_checker.py         # 数据安全检查
├── config.py                 # 配置管理
├── version_manager.py        # 版本管理
├── cli.py                    # 命令行接口
└── migrations/               # 迁移文件目录
    └── migration_history.json
```

---

## 6. CLI 使用示例

```bash
# 生成迁移
python -m migration generate \
    --from SQL/server_dump.sql \
    --to SQL/local_schema.sql \
    --dialect mysql \
    --output migrations/

# 检查安全
python -m migration check \
    --from SQL/server_dump.sql \
    --to SQL/local_schema.sql \
    --dialect mysql

# 应用迁移
python -m migration apply \
    --version 20260301120000 \
    --database mysql://user:pass@localhost/db

# 回滚迁移
python -m migration rollback \
    --version 20260301120000 \
    --database mysql://user:pass@localhost/db

# 查看迁移状态
python -m migration status
```

---

## 7. 完整工作流程

```
┌─────────────────┐     ┌─────────────────┐
│  server.sql     │     │  local.sql      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│              Parser (sqlglot)            │
│  - 解析 DDL 语句                         │
│  - 构建 DatabaseSchema 对象              │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│              Comparator                  │
│  - 对比两个 Schema                       │
│  - 检测重命名                            │
│  - 检查类型兼容性                        │
│  - 生成 DiffOperation 列表              │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│           Safety Checker                 │
│  - 检查破坏性操作                        │
│  - 生成安全报告                          │
│  - 要求用户确认                          │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│              Generator                   │
│  - 拓扑排序操作顺序                      │
│  - 处理循环依赖                          │
│  - 生成 up.sql / down.sql               │
│  - 分方言处理                            │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│          Version Manager                 │
│  - 生成版本号                            │
│  - 写入迁移文件                          │
│  - 记录迁移历史                          │
└─────────────────────────────────────────┘
```
ENDOFCONTENT~