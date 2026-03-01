#!/usr/bin/env python3
"""
SchemaDiff - SQL Schema Diff and Migration Generator

Usage:
    python main.py <source_sql> <target_sql> [--dialect mysql]
"""
import argparse
import sys

from migration import parse_sql_file, SchemaDiff


def main():
    parser = argparse.ArgumentParser(
        description="SchemaDiff - Compare SQL schemas and generate migrations"
    )
    parser.add_argument("source", help="Source SQL file")
    parser.add_argument("target", help="Target SQL file")
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
    
    # Parse source schema
    print(f"Parsing source schema: {args.source}")
    source_schema = parse_sql_file(args.source, args.dialect)
    print(f"  Found {len(source_schema.tables)} tables")
    
    # Parse target schema
    print(f"Parsing target schema: {args.target}")
    target_schema = parse_sql_file(args.target, args.dialect)
    print(f"  Found {len(target_schema.tables)} tables")
    
    # Compare schemas
    print("\nComparing schemas...")
    diff = SchemaDiff(source_schema, target_schema)
    changes = diff.compare()
    print(f"  Found {len(changes)} changes")
    
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
