"""
Unit tests for SchemaDiff
"""
import unittest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration import (
    parse_sql_file,
    DatabaseSchema,
    Table,
    Column,
    ForeignKey,
    SchemaDiff
)


class TestSchemaParser(unittest.TestCase):
    """Test SQL parsing functionality"""
    
    def test_parse_users_v1(self):
        """Test parsing users_v1.sql"""
        schema = parse_sql_file("SQL/users_v1.sql", "mysql")
        self.assertEqual(len(schema.tables), 1)
        
        table_keys = list(schema.tables.keys())
        users = schema.tables.get(table_keys[0])
        self.assertIsNotNone(users)
        self.assertEqual(len(users.columns), 3)
        
        # Check column names
        col_names = [c.name for c in users.columns.values()]
        self.assertIn("id", col_names)
        self.assertIn("name", col_names)
        self.assertIn("email", col_names)
    
    def test_parse_users_v2(self):
        """Test parsing users_v2.sql with additional columns"""
        schema = parse_sql_file("SQL/users_v2.sql", "mysql")
        self.assertEqual(len(schema.tables), 1)
        
        table_keys = list(schema.tables.keys())
        users = schema.tables.get(table_keys[0])
        self.assertEqual(len(users.columns), 5)
        
        col_names = [c.name for c in users.columns.values()]
        self.assertIn("phone", col_names)
        self.assertIn("created_at", col_names)
    
    def test_parse_orders_with_fk(self):
        """Test parsing orders.sql with foreign key"""
        schema = parse_sql_file("SQL/orders.sql", "mysql")
        self.assertEqual(len(schema.tables), 1)
        
        table_keys = list(schema.tables.keys())
        orders = schema.tables.get(table_keys[0])
        self.assertGreaterEqual(len(orders.columns), 4)


class TestSchemaDiff(unittest.TestCase):
    """Test schema comparison functionality"""
    
    def test_detect_column_addition(self):
        """Test detection of added columns"""
        source = parse_sql_file("SQL/users_v1.sql", "mysql")
        target = parse_sql_file("SQL/users_v2.sql", "mysql")
        
        diff = SchemaDiff(source, target)
        changes = diff.compare()
        
        # Should detect added columns: phone, created_at
        self.assertGreaterEqual(len(changes), 2)
    
    def test_generate_migration(self):
        """Test migration SQL generation"""
        source = parse_sql_file("SQL/users_v1.sql", "mysql")
        target = parse_sql_file("SQL/users_v2.sql", "mysql")
        
        diff = SchemaDiff(source, target)
        diff.compare()  # Must call compare first
        migration = diff.generate_migration()
        
        # Migration should contain ALTER TABLE statements
        self.assertIn("ALTER TABLE", migration)
        self.assertIn("ADD COLUMN", migration)


class TestSchemaModels(unittest.TestCase):
    """Test schema model classes"""
    
    def test_column_creation(self):
        """Test Column creation"""
        col = Column("id", "INT")
        self.assertEqual(col.name, "id")
        self.assertEqual(col.data_type, "INT")
        self.assertTrue(col.nullable)
    
    def test_table_columns_dict(self):
        """Test Table columns are stored in dict"""
        table = Table("users")
        table.columns["id"] = Column("id", "INT")
        table.columns["name"] = Column("name", "VARCHAR(100)")
        
        self.assertIn("id", table.columns)
        self.assertIn("name", table.columns)
        self.assertEqual(len(table.columns), 2)


if __name__ == "__main__":
    unittest.main()
