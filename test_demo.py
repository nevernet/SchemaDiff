#!/usr/bin/env python3
"""
SchemaDiff Demo - Test Script

Demonstrates:
1. Parsing SQL files
2. Comparing two version differences
3. Generating migration SQL
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from migration import parse_sql_file, SchemaDiff


def get_table_name(table_key):
    """Extract table name as string from sqlglot expression"""
    if hasattr(table_key, 'this') and hasattr(table_key.this, 'this'):
        return table_key.this.this
    if hasattr(table_key, 'this'):
        if hasattr(table_key.this, 'this'):
            return table_key.this.this
        return str(table_key.this)
    return str(table_key)


def demo_parse_sql():
    """Demo: Parse SQL files"""
    print("=" * 60)
    print("Demo 1: Parsing SQL Files")
    print("=" * 60)
    
    # Parse users_v1
    schema_v1 = parse_sql_file("SQL/users_v1.sql", "mysql")
    table_keys = list(schema_v1.tables.keys())
    print(f"\n[users_v1.sql]")
    print(f"  Tables: {[get_table_name(k) for k in table_keys]}")
    
    users_v1 = schema_v1.tables.get(table_keys[0]) if table_keys else None
    if users_v1:
        print(f"  Columns: {[c.name for c in users_v1.columns.values()]}")
    
    # Parse users_v2
    schema_v2 = parse_sql_file("SQL/users_v2.sql", "mysql")
    table_keys = list(schema_v2.tables.keys())
    print(f"\n[users_v2.sql]")
    print(f"  Tables: {[get_table_name(k) for k in table_keys]}")
    
    users_v2 = schema_v2.tables.get(table_keys[0]) if table_keys else None
    if users_v2:
        print(f"  Columns: {[c.name for c in users_v2.columns.values()]}")
    
    # Parse orders
    schema_orders = parse_sql_file("SQL/orders.sql", "mysql")
    table_keys = list(schema_orders.tables.keys())
    print(f"\n[orders.sql]")
    print(f"  Tables: {[get_table_name(k) for k in table_keys]}")
    
    orders = schema_orders.tables.get(table_keys[0]) if table_keys else None
    if orders:
        print(f"  Columns: {[c.name for c in orders.columns.values()]}")
        print(f"  Foreign Keys: {[(fk.columns, fk.ref_table) for fk in orders.fks.values()]}")


def demo_compare_schemas():
    """Demo: Compare schema differences"""
    print("\n" + "=" * 60)
    print("Demo 2: Comparing Schema Differences")
    print("=" * 60)
    
    source = parse_sql_file("SQL/users_v1.sql", "mysql")
    target = parse_sql_file("SQL/users_v2.sql", "mysql")
    
    diff = SchemaDiff(source, target)
    changes = diff.compare()
    
    print(f"\nFound {len(changes)} changes:")
    for i, change in enumerate(changes, 1):
        print(f"  {i}. {change}")


def demo_generate_migration():
    """Demo: Generate migration SQL"""
    print("\n" + "=" * 60)
    print("Demo 3: Generating Migration SQL")
    print("=" * 60)
    
    source = parse_sql_file("SQL/users_v1.sql", "mysql")
    target = parse_sql_file("SQL/users_v2.sql", "mysql")
    
    diff = SchemaDiff(source, target)
    changes = diff.compare()  # Must call compare first
    migration = diff.generate_migration()
    
    print("\n--- Migration Script ---")
    print(migration if migration else "-- No migration needed")


def demo_full_workflow():
    """Demo: Full workflow with all tables"""
    print("\n" + "=" * 60)
    print("Demo 4: Full Workflow - orders table analysis")
    print("=" * 60)
    
    schema_orders = parse_sql_file("SQL/orders.sql", "mysql")
    table_keys = list(schema_orders.tables.keys())
    orders = schema_orders.tables.get(table_keys[0]) if table_keys else None
    
    if orders:
        table_name = get_table_name(table_keys[0])
        print(f"\nOrders table structure:")
        print(f"  Table: {table_name}")
        print(f"  Columns:")
        for col in orders.columns.values():
            nullable = "" if col.nullable else " NOT NULL"
            print(f"    - {col.name}: {col.data_type}{nullable}")
        
        print(f"\nForeign Keys:")
        for fk in orders.fks.values():
            print(f"  {fk.columns} -> {fk.ref_table}.{fk.ref_columns}")


def main():
    print("SchemaDiff Demo - Testing Schema Parsing & Migration")
    print("=" * 60)
    
    # Run all demos
    demo_parse_sql()
    demo_compare_schemas()
    demo_generate_migration()
    demo_full_workflow()
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
