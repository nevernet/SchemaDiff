"""
Schema Comparator for SchemaDiff.
Compares two DatabaseSchema objects and generates migration scripts.
"""
from typing import List, Dict, Any, Set
from .schema_models import DatabaseSchema, Table, Column, Index, ForeignKey


class SchemaDiff:
    """Compare two database schemas and generate migration changes."""
    
    def __init__(self, source: DatabaseSchema, target: DatabaseSchema):
        self.source = source
        self.target = target
        self.changes: List[Dict[str, Any]] = []
    
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
        
        # Compare columns
        self._compare_columns(table_name, source_table, target_table)
        
        # Compare indexes
        self._compare_indexes(table_name, source_table, target_table)
        
        # Compare foreign keys
        self._compare_foreign_keys(table_name, source_table, target_table)
    
    def _compare_columns(self, table_name: str, source_table: Table, target_table: Table):
        """Compare columns between source and target tables."""
        source_cols = set(source_table.columns.keys())
        target_cols = set(target_table.columns.keys())
        
        # Add new columns
        for col_name in target_cols - source_cols:
            col = target_table.columns[col_name]
            self.changes.append({
                "type": "add_column",
                "table": table_name,
                "column": col_name,
                "definition": col
            })
        
        # Drop columns
        for col_name in source_cols - target_cols:
            self.changes.append({
                "type": "drop_column",
                "table": table_name,
                "column": col_name
            })
        
        # Compare existing columns
        for col_name in source_cols & target_cols:
            self._compare_column(table_name, col_name, 
                             source_table.columns[col_name],
                             target_table.columns[col_name])
    
    def _compare_column(self, table_name: str, col_name: str, 
                       source_col: Column, target_col: Column):
        """Compare a single column."""
        changes = {}
        
        # Type change
        if source_col.data_type != target_col.data_type:
            changes["type"] = target_col.data_type
        
        # Nullable change
        if source_col.nullable != target_col.nullable:
            changes["nullable"] = target_col.nullable
        
        # Default change
        if source_col.default != target_col.default:
            changes["default"] = target_col.default
        
        # Comment change
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
        
        # Add indexes
        for idx_name in target_idx - source_idx:
            idx = target_table.indexes[idx_name]
            self.changes.append({
                "type": "add_index",
                "table": table_name,
                "index": idx_name,
                "definition": idx
            })
        
        # Drop indexes
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
        
        # Add foreign keys
        for fk_name in target_fk - source_fk:
            fk = target_table.fks[fk_name]
            self.changes.append({
                "type": "add_fk",
                "table": table_name,
                "fk": fk_name,
                "definition": fk
            })
        
        # Drop foreign keys
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
        
        # Topological sort for correct FK order
        operations = self._order_operations()
        
        statements = []
        statements.append("-- Migration generated by SchemaDiff")
        statements.append("-- Generated at: " + str(__import__('datetime').datetime.now()))
        statements.append("")
        statements.append("BEGIN;")
        
        # DROP operations first (in reverse dependency order)
        for op in operations:
            if op["type"] == "drop_table":
                statements.append(f"DROP TABLE IF EXISTS `{op['table']}`;")
            elif op["type"] == "drop_column":
                statements.append(f"ALTER TABLE `{op['table']}` DROP COLUMN `{op['column']}`;")
            elif op["type"] == "drop_index":
                statements.append(f"DROP INDEX `{op['index']}` ON `{op['table']}`;")
            elif op["type"] == "drop_fk":
                statements.append(f"ALTER TABLE `{op['table']}` DROP FOREIGN KEY `{op['fk']}`;")
        
        # CREATE and ADD operations
        for op in operations:
            if op["type"] == "create_table":
                statements.append(f"-- CREATE TABLE {op['table']} (not fully implemented)")
            elif op["type"] == "add_column":
                col = op["definition"]
                stmt = f"ALTER TABLE `{op['table']}` ADD COLUMN `{col.name}` {col.data_type}"
                if not col.nullable:
                    stmt += " NOT NULL"
                if col.default:
                    stmt += f" DEFAULT {col.default}"
                stmt += ";"
                statements.append(stmt)
            elif op["type"] == "add_index":
                idx = op["definition"]
                unique = "UNIQUE " if idx.unique else ""
                cols = ", ".join(f"`{c}`" for c in idx.columns)
                statements.append(f"CREATE {unique}INDEX `{idx.name}` ON `{op['table']}` ({cols});")
            elif op["type"] == "add_fk":
                fk = op["definition"]
                cols = ", ".join(f"`{c}`" for c in fk.columns)
                ref_cols = ", ".join(f"`{c}`" for c in fk.ref_columns)
                stmt = f"ALTER TABLE `{op['table']}` ADD CONSTRAINT `{fk.name}` FOREIGN KEY ({cols}) REFERENCES `{fk.ref_table}` ({ref_cols})"
                if fk.on_delete:
                    stmt += f" ON DELETE {fk.on_delete}"
                stmt += ";"
                statements.append(stmt)
            elif op["type"] == "alter_column":
                col = op["new"]
                stmt = f"ALTER TABLE `{op['table']}` MODIFY COLUMN `{op['column']}` {col.data_type}"
                if not col.nullable:
                    stmt += " NOT NULL"
                if col.default:
                    stmt += f" DEFAULT {col.default}"
                stmt += ";"
                statements.append(stmt)
        
        statements.append("COMMIT;")
        
        return "\n".join(statements)
    
    def _order_operations(self) -> List[Dict[str, Any]]:
        """Order operations for correct FK dependency."""
        # Separate DROP and CREATE operations
        drops = [op for op in self.changes if op["type"].startswith("drop")]
        adds = [op for op in self.changes if not op["type"].startswith("drop")]
        
        # For drops, reverse topological order (dependencies first)
        drops.reverse()
        
        return drops + adds
