"""
Schema Comparator for SchemaDiff.
Compares two DatabaseSchema objects and generates migration scripts.
"""
from typing import List, Dict, Any, Set
from .schema_models import DatabaseSchema, Table, Column, Index, ForeignKey


class SchemaDiff:
    """Compare two database schemas and generate migration changes."""
    
    # Identifier quote characters by dialect
    QUOTE_CHAR = {
        "mysql": "`",
        "postgres": '"',
        "postgresql": '"',
    }
    
    def __init__(self, source: DatabaseSchema, target: DatabaseSchema, dialect: str = "mysql"):
        self.source = source
        self.target = target
        self.dialect = dialect
        self.changes: List[Dict[str, Any]] = []
    
    def _quote(self, name: str) -> str:
        """Quote an identifier based on dialect."""
        q = self.QUOTE_CHAR.get(self.dialect, "`")
        return f"{q}{name}{q}"
    
    def compare(self) -> List[Dict[str, Any]]:
        """Compare source and target schemas."""
        self.changes = []
        
        # Find tables to create
        for table_name, table in self.target.tables.items():
            if table_name not in self.source.tables:
                self.changes.append({
                    "type": "create_table",
                    "table": table_name,
                    "definition": table
                })
        
        # Find tables to drop
        for table_name in self.source.tables:
            if table_name not in self.target.tables:
                self.changes.append({
                    "type": "drop_table",
                    "table": table_name
                })
        
        # Compare existing tables
        for table_name in set(self.source.tables.keys()) & set(self.target.tables.keys()):
            self._compare_table(table_name)
        
        return self.changes
    
    def _compare_table(self, table_name: str):
        """Compare columns, indexes, and foreign keys of a table."""
        source_table = self.source.tables[table_name]
        target_table = self.target.tables[table_name]
        
        self._compare_columns(table_name, source_table, target_table)
        self._compare_indexes(table_name, source_table, target_table)
        self._compare_foreign_keys(table_name, source_table, target_table)
    
    def _compare_columns(self, table_name: str, source_table: Table, target_table: Table):
        """Compare columns between source and target tables."""
        source_cols = set(source_table.columns.keys())
        target_cols = set(target_table.columns.keys())
        
        for col_name in target_cols - source_cols:
            col = target_table.columns[col_name]
            self.changes.append({
                "type": "add_column",
                "table": table_name,
                "column": col_name,
                "definition": col
            })
        
        for col_name in source_cols - target_cols:
            self.changes.append({
                "type": "drop_column",
                "table": table_name,
                "column": col_name
            })
        
        for col_name in source_cols & target_cols:
            self._compare_column(table_name, col_name, 
                             source_table.columns[col_name],
                             target_table.columns[col_name])
    
    def _compare_column(self, table_name: str, col_name: str, 
                       source_col: Column, target_col: Column):
        """Compare a single column."""
        changes = {}
        
        if source_col.data_type != target_col.data_type:
            changes["type"] = target_col.data_type
        if source_col.nullable != target_col.nullable:
            changes["nullable"] = target_col.nullable
        if source_col.default != target_col.default:
            changes["default"] = target_col.default
        if source_col.comment != target_col.comment:
            changes["comment"] = target_col.comment
        
        if changes:
            self.changes.append({
                "type": "alter_column",
                "table": table_name,
                "column": col_name,
                "old": source_col,
                "new": target_col,
                "changes": changes
            })
    
    def _compare_indexes(self, table_name: str, source_table: Table, target_table: Table):
        """Compare indexes between source and target tables."""
        source_idx = set(source_table.indexes.keys())
        target_idx = set(target_table.indexes.keys())
        
        for idx_name in target_idx - source_idx:
            idx = target_table.indexes[idx_name]
            self.changes.append({
                "type": "add_index",
                "table": table_name,
                "index": idx_name,
                "definition": idx
            })
        
        for idx_name in source_idx - target_idx:
            self.changes.append({
                "type": "drop_index",
                "table": table_name,
                "index": idx_name
            })
    
    def _compare_foreign_keys(self, table_name: str, source_table: Table, target_table: Table):
        """Compare foreign keys between source and target tables."""
        source_fk = set(source_table.fks.keys())
        target_fk = set(target_table.fks.keys())
        
        for fk_name in target_fk - source_fk:
            fk = target_table.fks[fk_name]
            self.changes.append({
                "type": "add_fk",
                "table": table_name,
                "fk": fk_name,
                "definition": fk
            })
        
        for fk_name in source_fk - target_fk:
            self.changes.append({
                "type": "drop_fk",
                "table": table_name,
                "fk": fk_name
            })
    
    def generate_migration(self) -> str:
        """Generate migration SQL script."""
        if not self.changes:
            return "-- No changes detected"
        
        operations = self._order_operations()
        
        statements = []
        statements.append("-- Migration generated by SchemaDiff")
        statements.append(f"-- Dialect: {self.dialect}")
        statements.append("-- Generated at: " + str(__import__('datetime').datetime.now()))
        statements.append("")
        
        if self.dialect in ("postgres", "postgresql"):
            statements.append("BEGIN;")
        
        for op in operations:
            stmt = self._generate_drop_statement(op)
            if stmt:
                statements.append(stmt)
        
        for op in operations:
            stmt = self._generate_add_statement(op)
            if stmt:
                statements.append(stmt)
        
        statements.append("COMMIT;")
        
        return "\n".join(statements)
    
    def _generate_drop_statement(self, op: Dict[str, Any]) -> str:
        t = op["type"]
        table = self._quote(op["table"])
        
        if t == "drop_table":
            return f"DROP TABLE IF EXISTS {table};"
        elif t == "drop_column":
            col = self._quote(op["column"])
            return f"ALTER TABLE {table} DROP COLUMN {col};"
        elif t == "drop_index":
            idx = self._quote(op["index"])
            if self.dialect in ("postgres", "postgresql"):
                return f"DROP INDEX IF EXISTS {idx};"
            else:
                return f"DROP INDEX {idx} ON {table};"
        elif t == "drop_fk":
            fk = self._quote(op["fk"])
            if self.dialect in ("postgres", "postgresql"):
                return f"ALTER TABLE {table} DROP CONSTRAINT {fk};"
            else:
                return f"ALTER TABLE {table} DROP FOREIGN KEY {fk};"
        return ""
    
    def _generate_add_statement(self, op: Dict[str, Any]) -> str:
        t = op["type"]
        table = self._quote(op["table"])
        
        if t == "create_table":
            return self._generate_create_table(op["definition"])
        elif t == "add_column":
            col = op["definition"]
            col_def = self._format_column_def(col)
            return f"ALTER TABLE {table} ADD COLUMN {col_def};"
        elif t == "add_index":
            idx = op["definition"]
            unique = "UNIQUE " if idx.unique else ""
            cols = ", ".join(self._quote(c) for c in idx.columns)
            idx_name = self._quote(idx.name)
            return f"CREATE {unique}INDEX {idx_name} ON {table} ({cols});"
        elif t == "add_fk":
            fk = op["definition"]
            cols = ", ".join(self._quote(c) for c in fk.columns)
            ref_cols = ", ".join(self._quote(c) for c in fk.ref_columns)
            ref_table = self._quote(fk.ref_table)
            fk_name = self._quote(fk.name)
            stmt = f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})"
            if fk.on_delete:
                stmt += f" ON DELETE {fk.on_delete}"
            stmt += ";"
            return stmt
        elif t == "alter_column":
            col = op["new"]
            col_def = self._format_column_def(col)
            col_name = self._quote(op["column"])
            if self.dialect in ("postgres", "postgresql"):
                return f"ALTER TABLE {table} ALTER COLUMN {col_name} TYPE {col.data_type};"
            else:
                return f"ALTER TABLE {table} MODIFY COLUMN {col_def};"
        return ""
    
    def _format_column_def(self, col: Column) -> str:
        col_name = self._quote(col.name)
        dtype = col.data_type
        
        # Handle PostgreSQL SERIAL
        if self.dialect in ("postgres", "postgresql") and col.auto_increment:
            if dtype.upper() in ("INT", "INTEGER"):
                dtype = "SERIAL"
            elif dtype.upper() in ("BIGINT",):
                dtype = "BIGSERIAL"
        
        parts = [f"{col_name} {dtype}"]
        
        if not col.nullable:
            parts.append("NOT NULL")
        if col.default:
            parts.append(f"DEFAULT {col.default}")
        if col.auto_increment and self.dialect not in ("postgres", "postgresql"):
            parts.append("AUTO_INCREMENT")
        
        return " ".join(parts)
    
    def _generate_create_table(self, table: Table) -> str:
        table_name = self._quote(table.name)
        
        col_defs = []
        for col in table.columns.values():
            col_defs.append(self._format_column_def(col))
        
        if table.primary_key:
            pk_cols = ", ".join(self._quote(c) for c in table.primary_key)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")
        
        for idx in table.indexes.values():
            unique = "UNIQUE " if idx.unique else ""
            cols = ", ".join(self._quote(c) for c in idx.columns)
            col_defs.append(f"{unique}INDEX {self._quote(idx.name)} ({cols})")
        
        for fk in table.fks.values():
            cols = ", ".join(self._quote(c) for c in fk.columns)
            ref_cols = ", ".join(self._quote(c) for c in fk.ref_columns)
            ref_table = self._quote(fk.ref_table)
            fk_def = f"CONSTRAINT {self._quote(fk.name)} FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})"
            if fk.on_delete:
                fk_def += f" ON DELETE {fk.on_delete}"
            col_defs.append(fk_def)
        
        cols_str = ",\n  ".join(col_defs)
        
        opts = []
        if table.engine and self.dialect == "mysql":
            opts.append(f"ENGINE={table.engine}")
        if table.charset and self.dialect == "mysql":
            opts.append(f"DEFAULT CHARSET={table.charset}")
        
        sql = f"CREATE TABLE {table_name} (\n  {cols_str}\n)"
        if opts:
            sql += " " + " ".join(opts)
        sql += ";"
        
        return sql
    
    def _order_operations(self) -> List[Dict[str, Any]]:
        drops = [op for op in self.changes if op["type"].startswith("drop")]
        adds = [op for op in self.changes if not op["type"].startswith("drop")]
        drops.reverse()
        return drops + adds
