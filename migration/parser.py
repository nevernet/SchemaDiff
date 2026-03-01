"""
SQL Parser for SchemaDiff.
Supports MySQL and PostgreSQL dialects.
"""
import sqlglot
from sqlglot import exp
from typing import Optional
from collections import OrderedDict

from .schema_models import (
    DatabaseSchema, Table, Column, Index, ForeignKey
)


def parse_sql_file(file_path: str, dialect: str = "mysql") -> DatabaseSchema:
    """
    Parse SQL file and extract database schema.
    
    Args:
        file_path: Path to SQL file
        dialect: SQL dialect (mysql, postgres, etc.)
    
    Returns:
        DatabaseSchema object containing all parsed tables
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        sql_text = f.read()
    return parse_sql_text(sql_text, dialect)


def parse_sql_text(sql_text: str, dialect: str = "mysql") -> DatabaseSchema:
    """
    Parse SQL text and extract database schema.
    
    Args:
        sql_text: SQL content
        dialect: SQL dialect (mysql, postgres, etc.)
    
    Returns:
        DatabaseSchema object containing all parsed tables
    """
    schema = DatabaseSchema()
    
    # Parse SQL statements
    statements = sqlglot.parse(sql_text, dialect=dialect)
    
    for stmt in statements:
        if isinstance(stmt, exp.Create):
            # Handle CREATE TABLE statements
            if isinstance(stmt.this, exp.Schema):
                table = _parse_create_table(stmt, dialect)
                if table:
                    schema.tables[table.name] = table
    
    return schema


def _parse_create_table(stmt: exp.Create, dialect: str) -> Optional[Table]:
    """Parse a CREATE TABLE statement into a Table object."""
    schema_obj = stmt.this
    if not isinstance(schema_obj, exp.Schema):
        return None
    
    table_node = schema_obj.this
    if not isinstance(table_node, exp.Table):
        return None
    
    table_name = table_node.name
    
    table = Table(name=table_name)
    
    # Parse columns from schema expressions
    if schema_obj.expressions:
        for col_expr in schema_obj.expressions:
            if isinstance(col_expr, exp.ColumnDef):
                column = _parse_column(col_expr, dialect)
                if column:
                    table.columns[column.name] = column
    
    # Parse primary key from constraints
    for col_expr in schema_obj.expressions:
        if isinstance(col_expr, exp.ColumnDef):
            if col_expr.constraints:
                for constraint in col_expr.constraints:
                    if isinstance(constraint.kind, exp.PrimaryKeyColumnConstraint):
                        if table.primary_key is None:
                            table.primary_key = []
                        table.primary_key.append(col_expr.this.name)
    
    return table


def _parse_column(col_def: exp.ColumnDef, dialect: str) -> Optional[Column]:
    """Parse a column definition."""
    name = col_def.this.name if col_def.this else None
    if not name:
        return None
    
    # Get data type
    data_type = "UNKNOWN"
    if col_def.kind:
        type_obj = col_def.kind
        if isinstance(type_obj, exp.DataType):
            data_type = type_obj.this.name.upper()
            # Handle VARCHAR(50) style types
            if type_obj.expressions:
                params = []
                for p in type_obj.expressions:
                    if hasattr(p, 'this'):
                        params.append(str(p.this))
                    else:
                        params.append(str(p))
                if params:
                    data_type += f"({', '.join(params)})"
    
    # Get constraints
    nullable = True
    default = None
    auto_increment = False
    comment = None
    
    if col_def.constraints:
        for constraint in col_def.constraints:
            # Check NOT NULL
            if isinstance(constraint.kind, exp.NotNullColumnConstraint):
                nullable = False
            
            # Check DEFAULT
            elif isinstance(constraint.kind, exp.DefaultColumnConstraint):
                if constraint.kind.this:
                    default = constraint.kind.this.sql(dialect=dialect)
            
            # Check AUTO_INCREMENT
            elif isinstance(constraint.kind, exp.AutoIncrementColumnConstraint):
                auto_increment = True
            
            # Check COMMENT
            elif isinstance(constraint.kind, exp.CommentColumnConstraint):
                if constraint.kind.this:
                    comment_val = constraint.kind.this
                    if hasattr(comment_val, 'this'):
                        comment = comment_val.this
                    else:
                        comment = str(comment_val)
    
    return Column(
        name=name,
        data_type=data_type,
        nullable=nullable,
        default=default,
        auto_increment=auto_increment,
        comment=comment
    )
