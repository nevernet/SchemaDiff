"""
SQL Parser for SchemaDiff.
Supports MySQL and PostgreSQL dialects.
"""
import sqlglot
from sqlglot import exp
from typing import Optional

from .schema_models import (
    DatabaseSchema, Table, Column, Index, ForeignKey
)


def parse_sql_file(file_path: str, dialect: str = "mysql") -> DatabaseSchema:
    """Parse SQL file and extract database schema."""
    with open(file_path, 'r', encoding='utf-8') as f:
        sql_text = f.read()
    return parse_sql_text(sql_text, dialect)


def parse_sql_text(sql_text: str, dialect: str = "mysql") -> DatabaseSchema:
    """Parse SQL text and extract database schema."""
    schema = DatabaseSchema()
    
    statements = sqlglot.parse(sql_text, dialect=dialect)
    
    for stmt in statements:
        if stmt is None:
            continue
        
        # Handle CREATE TABLE
        if isinstance(stmt, exp.Create) and stmt.kind == "TABLE":
            table = _parse_create_table(stmt, dialect)
            if table:
                schema.tables[table.name] = table
        
        # Handle CREATE INDEX
        elif isinstance(stmt, exp.Create) and stmt.kind == "INDEX":
            index = _parse_index_expr(stmt, dialect)
            if index:
                table_name = _find_table_for_index(schema, index)
                if table_name and table_name in schema.tables:
                    schema.tables[table_name].indexes[index.name] = index
    
    return schema


def _parse_create_table(stmt: exp.Create, dialect: str) -> Optional[Table]:
    """Parse a CREATE TABLE statement."""
    # Get table name
    table_name = None
    
    if hasattr(stmt.this, 'this'):
        table_name = stmt.this.this
    elif hasattr(stmt.this, 'name'):
        table_name = stmt.this.name
    
    if not table_name:
        return None
    
    table = Table(name=table_name)
    
    # Get expressions
    expressions = []
    if hasattr(stmt.this, 'expressions'):
        expressions = stmt.this.expressions
    
    for item in expressions:
        if isinstance(item, exp.ColumnDef):
            column = _parse_column_def(item, dialect)
            if column:
                table.columns[column.name] = column
        elif isinstance(item, exp.Constraint):
            _parse_constraint(item, table, dialect)
        elif isinstance(item, exp.ForeignKey):
            fk = _parse_foreign_key(item, dialect)
            if fk:
                table.fks[fk.name] = fk
    
    return table


def _parse_column_def(col_def: exp.ColumnDef, dialect: str) -> Optional[Column]:
    """Parse a column definition."""
    name = col_def.name
    if not name:
        return None
    
    # Get data type
    data_type = "UNKNOWN"
    kind = col_def.args.get("kind")
    if kind:
        data_type = kind.name.upper()
    
    # Get nullable
    nullable = True
    constraints = col_def.constraints
    if constraints:
        for c in constraints:
            if isinstance(c, (exp.NotNullColumnConstraint)):
                nullable = False
    
    # Get default
    default = None
    if constraints:
        for c in constraints:
            if isinstance(c, exp.DefaultColumnConstraint):
                default = c.this.sql(dialect=dialect) if c.this else None
    
    # Get auto_increment
    auto_increment = False
    if constraints:
        for c in constraints:
            if isinstance(c, exp.AutoIncrementColumnConstraint):
                auto_increment = True
    
    return Column(
        name=name,
        data_type=data_type,
        nullable=nullable,
        default=default,
        auto_increment=auto_increment
    )


def _parse_constraint(constraint: exp, table: Table, dialect: str):
    """Parse table-level constraints."""
    if isinstance(constraint, exp.PrimaryKeyConstraint):
        cols = []
        if constraint.this and hasattr(constraint.this, 'expressions'):
            cols = [c.name for c in constraint.this.expressions]
        table.primary_key = cols
    
    elif isinstance(constraint, exp.UniqueConstraint):
        cols = []
        if constraint.this and hasattr(constraint.this, 'expressions'):
            cols = [c.name for c in constraint.this.expressions]
        if cols:
            idx = Index(name=f"uk_{cols[0]}", columns=cols, unique=True)
            table.indexes[idx.name] = idx
    
    elif isinstance(constraint, exp.ForeignKey):
        fk = _parse_foreign_key(constraint, dialect)
        if fk:
            table.fks[fk.name] = fk


def _parse_foreign_key(fk_expr: exp.ForeignKey, dialect: str) -> Optional[ForeignKey]:
    """Parse a ForeignKey expression."""
    name = "fk_auto"
    if fk_expr.args.get("name"):
        name = str(fk_expr.args.get("name"))
    
    columns = []
    if fk_expr.expressions:
        for c in fk_expr.expressions:
            if hasattr(c, "name"):
                columns.append(c.name)
            else:
                columns.append(str(c))
    
    ref = fk_expr.args.get("reference")
    if not ref:
        return None
    
    ref_table = ref.name if hasattr(ref, "name") else str(ref)
    
    ref_columns = []
    if hasattr(ref, "expressions") and ref.expressions:
        for c in ref.expressions:
            ref_columns.append(c.name if hasattr(c, "name") else str(c))
    
    on_delete = None
    ondel = fk_expr.args.get("ondelete")
    if ondel:
        on_delete = str(ondel)
    
    return ForeignKey(
        name=name,
        columns=columns,
        ref_table=ref_table,
        ref_columns=ref_columns,
        on_delete=on_delete
    )


def _parse_index_expr(stmt: exp.Create, dialect: str) -> Optional[Index]:
    """Parse a CREATE INDEX statement."""
    index_node = stmt.this
    if not isinstance(index_node, exp.Index):
        return None
    
    name = index_node.name or "idx_auto"
    unique = bool(index_node.unique)
    kind = index_node.kind
    
    columns = []
    if index_node.expressions:
        for col in index_node.expressions:
            if isinstance(col, exp.IndexColumn):
                columns.append(col.name)
            elif isinstance(col, exp.Column):
                columns.append(col.name)
    
    return Index(name=name, columns=columns, unique=unique, index_type=kind)


def _find_table_for_index(schema: DatabaseSchema, index: Index) -> Optional[str]:
    """Try to find which table an index belongs to."""
    for table_name, table in schema.tables.items():
        for col in index.columns:
            if col in table.columns:
                return table_name
    return None
