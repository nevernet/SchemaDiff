"""
Schema Comparator for SchemaDiff.
Compares two DatabaseSchema objects and generates migration scripts.
"""
from typing import List, Dict, Any
from .schema_models import DatabaseSchema, Table, Column


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
        """Compare a single table."""
        source_table = self.source.tables[table_name]
        target_table = self.target.tables[table_name]
        
        # Find columns to add
        for col_name, col in target_table.columns.items():
            if col_name not in source_table.columns:
                self.changes.append({
                    "type": "add_column",
                    "table": table_name,
                    "column": col_name,
                    "definition": col
                })
        
        # Find columns to remove
        for col_name in source_table.columns:
            if col_name not in target_table.columns:
                self.changes.append({
                    "type": "drop_column",
                    "table": table_name,
                    "column": col_name
                })
        
        # Find columns to modify
        for col_name in set(source_table.columns.keys()) & set(target_table.columns.keys()):
            source_col = source_table.columns[col_name]
            target_col = target_table.columns[col_name]
            
            if self._column_changed(source_col, target_col):
                self.changes.append({
                    "type": "modify_column",
                    "table": table_name,
                    "column": col_name,
                    "old_definition": source_col,
                    "new_definition": target_col
                })
    
    def _column_changed(self, source: Column, target: Column) -> bool:
        """Check if a column definition has changed."""
        return (
            source.data_type != target.data_type or
            source.nullable != target.nullable or
            source.default != target.default
        )
    
    def generate_migration(self) -> str:
        """Generate migration SQL script."""
        changes = self.compare()
        
        statements = []
        for change in changes:
            change_type = change["type"]
            
            if change_type == "create_table":
                statements.append(self._generate_create_table(change["definition"]))
            elif change_type == "drop_table":
                statements.append(f"DROP TABLE {change['table']};")
            elif change_type == "add_column":
                statements.append(self._generate_add_column(change["table"], change["definition"]))
            elif change_type == "drop_column":
                statements.append(f"ALTER TABLE {change['table']} DROP COLUMN {change['column']};")
            elif change_type == "modify_column":
                statements.append(self._generate_modify_column(
                    change["table"], 
                    change["old_definition"], 
                    change["new_definition"]
                ))
        
        return "\n\n".join(statements)
    
    def _generate_create_table(self, table: Table) -> str:
        """Generate CREATE TABLE statement."""
        lines = [f"CREATE TABLE {table.name} ("]
        
        col_defs = []
        for col in table.columns.values():
            col_def = f"  {col.name} {col.data_type}"
            if not col.nullable:
                col_def += " NOT NULL"
            if col.default:
                col_def += f" DEFAULT {col.default}"
            if col.auto_increment:
                col_def += " AUTO_INCREMENT"
            col_defs.append(col_def)
        
        if table.primary_key:
            lines.append(",\n".join(col_defs))
            lines.append(f", PRIMARY KEY ({', '.join(table.primary_key)})")
        else:
            lines.append(",\n".join(col_defs))
        
        lines.append(");")
        return "\n".join(lines)
    
    def _generate_add_column(self, table_name: str, column: Column) -> str:
        """Generate ALTER TABLE ADD COLUMN statement."""
        col_def = f"{column.name} {column.data_type}"
        if not column.nullable:
            col_def += " NOT NULL"
        if column.default:
            col_def += f" DEFAULT {column.default}"
        
        return f"ALTER TABLE {table_name} ADD COLUMN {col_def};"
    
    def _generate_modify_column(self, table_name: str, old_col: Column, new_col: Column) -> str:
        """Generate ALTER TABLE MODIFY COLUMN statement."""
        col_def = f"{new_col.name} {new_col.data_type}"
        if not new_col.nullable:
            col_def += " NOT NULL"
        if new_col.default:
            col_def += f" DEFAULT {new_col.default}"
        
        return f"ALTER TABLE {table_name} MODIFY COLUMN {col_def};"
