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
        table_name = stmt.this.this.name if hasattr(stmt.this.this, "name") else stmt.this.this
    elif hasattr(stmt.this, 'name'):
        table_name = stmt.this.name
    
    if not table_name:
        return None
    
    table = Table(name=table_name)
    
    # Get expressions
    expressions = []
    if hasattr(stmt.this, 'expressions'):
        expressions = stmt.this.expressions
    
    # First pass: parse columns
    for item in expressions:
        if isinstance(item, exp.ColumnDef):
            column = _parse_column_def(item, dialect)
            if column:
                table.columns[column.name] = column
                # Check for column-level REFERENCES
                if item.constraints:
                    for c in item.constraints:
                        # Check if it's a ColumnConstraint with kind=Reference
                        ref_obj = None
                        if isinstance(c, exp.ColumnConstraint):
                            kind = c.args.get("kind")
                            if isinstance(kind, exp.Reference):
                                ref_obj = kind
                        elif isinstance(c, exp.Reference):
                            ref_obj = c
                        
                        if ref_obj:
                            ref = ref_obj.args.get("this")
                            if ref:
                                ref_table = None
                                ref_columns = []
                                if hasattr(ref, 'this') and hasattr(ref.this, 'name'):
                                    ref_table = ref.this.name
                                if hasattr(ref, 'expressions') and ref.expressions:
                                    for col in ref.expressions:
                                        if hasattr(col, 'name'):
                                            ref_columns.append(col.name)
                                fk = ForeignKey(
                                    name=f"fk_{column.name}",
                                    columns=[column.name],
                                    ref_table=ref_table,
                                    ref_columns=ref_columns
                                )
                                table.fks[fk.name] = fk
        elif isinstance(item, exp.Constraint):
            _parse_constraint(item, table, dialect)
        elif isinstance(item, exp.PrimaryKeyColumnConstraint):
            _parse_constraint(item, table, dialect)
        elif isinstance(item, exp.UniqueColumnConstraint):
            _parse_constraint(item, table, dialect)
        elif isinstance(item, exp.IndexColumnConstraint):
            _parse_constraint(item, table, dialect)
        elif isinstance(item, exp.ForeignKey):
            fk = _parse_foreign_key(item, dialect)
            if fk:
                table.fks[fk.name] = fk
        elif isinstance(item, (exp.UniqueColumnConstraint, exp.IndexColumnConstraint)):
            # Handle UNIQUE INDEX in CREATE TABLE expressions
            _parse_constraint(item, table, dialect)
    
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
        data_type = kind.sql(dialect=dialect).upper()
    
    # Get nullable
    nullable = True
    constraints = col_def.constraints
    fk_reference = None  # Column-level REFERENCES
    
    if constraints:
        for c in constraints:
            if isinstance(c, (exp.NotNullColumnConstraint)):
                nullable = False
            elif isinstance(c, exp.DefaultColumnConstraint):
                default = c.this.sql(dialect=dialect) if c.this else None
            elif isinstance(c, exp.AutoIncrementColumnConstraint):
                auto_increment = True
            elif isinstance(c, exp.Reference):
                # Column-level REFERENCES (e.g., user_id INT REFERENCES users(id))
                fk_reference = c
    
    # Re-parse constraints for defaults and auto_increment
    default = None
    auto_increment = False
    if constraints:
        for c in constraints:
            if isinstance(c, exp.DefaultColumnConstraint):
                default = c.this.sql(dialect=dialect) if c.this else None
            elif isinstance(c, exp.AutoIncrementColumnConstraint):
                auto_increment = True
    
    # Check for inline FK from column-level REFERENCES
    if fk_reference:
        ref = fk_reference.args.get("this")
        if ref:
            ref_table = None
            ref_columns = []
            if hasattr(ref, 'this') and hasattr(ref.this, 'name'):
                ref_table = ref.this.name
            if hasattr(ref, 'expressions') and ref.expressions:
                for c in ref.expressions:
                    if hasattr(c, 'name'):
                        ref_columns.append(c.name)
            
            # Create FK for this column
            fk = ForeignKey(
                name=f"fk_{name}",
                columns=[name],
                ref_table=ref_table,
                ref_columns=ref_columns
            )
            # This will be added to table.fks by caller
    
    return Column(
        name=name,
        data_type=data_type,
        nullable=nullable,
        default=default,
        auto_increment=auto_increment
    )


def _parse_constraint(constraint: exp, table: Table, dialect: str):
    """Parse table-level constraints."""
    # Handle IndexColumnConstraint (non-unique INDEX in CREATE TABLE)
    if isinstance(constraint, exp.IndexColumnConstraint):
        idx_name = None
        cols = []
        if constraint.this:
            idx_name = constraint.this.name if hasattr(constraint.this, 'name') else None
        if hasattr(constraint, 'expressions') and constraint.expressions:
            for c in constraint.expressions:
                if hasattr(c, 'this') and hasattr(c.this, 'name'):
                    cols.append(c.this.name)
                elif hasattr(c, 'name'):
                    cols.append(c.name)
                else:
                    cols.append(str(c))
        if idx_name and cols:
            idx = Index(name=idx_name, columns=cols, unique=False)
            table.indexes[idx.name] = idx
        return
    
    if isinstance(constraint, exp.PrimaryKeyColumnConstraint):
        # PRIMARY KEY (col1, col2) - table-level primary key
        cols = []
        if constraint.this and hasattr(constraint.this, 'expressions'):
            cols = [c.name for c in constraint.this.expressions]
        table.primary_key = cols
    
    elif isinstance(constraint, exp.UniqueColumnConstraint):
        # UNIQUE (col) or UNIQUE INDEX idx_name (col) - table-level unique
        # constraint.this is Schema: this=idx_name, expressions=[col1, col2]
        idx_name = None
        cols = []
        if constraint.this:
            # Check if this is a Schema with index name
            if hasattr(constraint.this, 'this') and hasattr(constraint.this.this, 'name'):
                idx_name = constraint.this.this.name
            # Check if this is a list of columns (not a Schema)
            elif hasattr(constraint.this, '__iter__'):
                for c in constraint.this:
                    if hasattr(c, 'name'):
                        cols.append(c.name)
                    else:
                        cols.append(str(c))
            # Schema.expressions contains the column list
            if hasattr(constraint.this, 'expressions') and constraint.this.expressions:
                cols = []
                for c in constraint.this.expressions:
                    if hasattr(c, 'name'):
                        cols.append(c.name)
                    else:
                        cols.append(str(c))
        # Generate index name if not provided
        if not idx_name and cols:
            idx_name = f"uk_{cols[0]}"
        if idx_name and cols:
            idx = Index(name=idx_name, columns=cols, unique=True)
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
    
    # ref is a Reference object: ref.args['this'] is Schema
    # Schema.this = Table (with table name)
    # Schema.expressions = list of column Identifiers
    ref_table = None
    if hasattr(ref, 'args') and ref.args.get('this'):
        schema = ref.args['this']
        if hasattr(schema, 'this') and hasattr(schema.this, 'name'):
            ref_table = schema.this.name
        elif hasattr(schema, 'this'):
            ref_table = schema.this
    
    ref_columns = []
    if hasattr(ref, 'args') and ref.args.get('this'):
        schema = ref.args['this']
        if hasattr(schema, 'expressions') and schema.expressions:
            for c in schema.expressions:
                if hasattr(c, 'name'):
                    ref_columns.append(c.name)
                else:
                    ref_columns.append(str(c))
    
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
