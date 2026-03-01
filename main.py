#!/usr/bin/env python3
"""
SchemaDiff - SQL Schema Diff and Migration Generator

Usage:
    # Single file comparison
    python main.py <source_sql> <target_sql> [--dialect mysql]
    
    # Directory comparison
    python main.py <source_dir> <target_dir> [--dialect mysql]
"""
import argparse
import sys
import os
from pathlib import Path

from migration import parse_sql_file, SchemaDiff, DatabaseSchema


def parse_sql_directory(dir_path: str, dialect: str = "mysql") -> DatabaseSchema:
    """Parse all SQL files in a directory."""
    schema = DatabaseSchema()
    dir_path = Path(dir_path)
    
    if not dir_path.exists():
        raise ValueError(f"Directory not found: {dir_path}")
    
    for sql_file in sorted(dir_path.glob("*.sql")):
        print(f"  Parsing: {sql_file.name}")
        try:
            file_schema = parse_sql_file(str(sql_file), dialect)
            for table_name, table in file_schema.tables.items():
                schema.tables[table_name] = table
        except Exception as e:
            print(f"    Warning: Failed to parse {sql_file.name}: {e}")
    
    return schema


def main():
    parser = argparse.ArgumentParser(
        description="SchemaDiff - Compare SQL schemas and generate migrations"
    )
    parser.add_argument("source", help="Source SQL file or directory")
    parser.add_argument("target", help="Target SQL file or directory")
    parser.add_argument(
        "--dialect", 
        default="mysql",
        choices=["mysql", "postgres", "postgresql"],
        help="SQL dialect (default: mysql)"
    )
    parser.add_argument(
        "--output", 
        "-o", 
        help="Output file for migration script"
    )
    
    args = parser.parse_args()
    
    # Detect if source/target is file or directory
    source_is_dir = os.path.isdir(args.source)
    target_is_dir = os.path.isdir(args.target)
    
    # Parse source
    if source_is_dir:
        print(f"Parsing source directory: {args.source}")
        source_schema = parse_sql_directory(args.source, args.dialect)
    else:
        print(f"Parsing source file: {args.source}")
        source_schema = parse_sql_file(args.source, args.dialect)
    print(f"  Found {len(source_schema.tables)} tables")
    
    # Parse target
    if target_is_dir:
        print(f"Parsing target directory: {args.target}")
        target_schema = parse_sql_directory(args.target, args.dialect)
    else:
        print(f"Parsing target file: {args.target}")
        target_schema = parse_sql_file(args.target, args.dialect)
    print(f"  Found {len(target_schema.tables)} tables")
    
    # Compare schemas
    print("\nComparing schemas...")
    diff = SchemaDiff(source_schema, target_schema)
    changes = diff.compare()
    print(f"  Found {len(changes)} changes")
    
    if not changes:
        print("\n✅ No differences found - schemas are identical!")
        return 0
    
    # Show changes summary
    print("\nChanges detected:")
    for c in changes:
        t = c.get('type', 'unknown')
        table = c.get('table', '')
        column = c.get('column', '')
        if t == 'add_column':
            print(f"  + ADD COLUMN: {table}.{column}")
        elif t == 'drop_column':
            print(f"  - DROP COLUMN: {table}.{column}")
        elif t == 'alter_column':
            print(f"  ~ ALTER COLUMN: {table}.{column}")
        elif t == 'create_table':
            print(f"  + CREATE TABLE: {table}")
        elif t == 'drop_table':
            print(f"  - DROP TABLE: {table}")
    
    # Generate migration
    migration = diff.generate_migration()
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(migration)
        print(f"\nMigration script written to: {args.output}")
    else:
        print("\n--- Migration Script ---")
        print(migration)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
