#!/usr/bin/env python3
"""
Database schema migration script.
Runs SQL migrations with support for CREATE IF NOT EXISTS patterns.
"""
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv
import os
import re

load_dotenv()

DATABASE_URL_SYNC = os.environ.get("DATABASE_URL_SYNC")
if not DATABASE_URL_SYNC:
    raise RuntimeError("DATABASE_URL_SYNC not found in .env")

# Path to SQL file
SQL_FILE_PATH = "app/database/migrations/001_initial_schema.sql"

def get_existing_tables(engine):
    """Get list of existing tables in the database."""
    inspector = inspect(engine)
    return set(inspector.get_table_names())

def modify_sql_for_idempotency(sql_content):
    """
    Modify SQL statements to be idempotent by adding IF NOT EXISTS clauses
    where applicable.
    """
    # Replace CREATE TABLE with CREATE TABLE IF NOT EXISTS
    sql_content = re.sub(
        r'CREATE TABLE\s+(\w+)\s*\(',
        r'CREATE TABLE IF NOT EXISTS \1 (',
        sql_content,
        flags=re.IGNORECASE
    )
    
    # Replace CREATE INDEX with CREATE INDEX IF NOT EXISTS
    sql_content = re.sub(
        r'CREATE INDEX\s+(\w+)\s+ON',
        r'CREATE INDEX IF NOT EXISTS \1 ON',
        sql_content,
        flags=re.IGNORECASE
    )
    
    # Replace CREATE VIEW with CREATE OR REPLACE VIEW
    sql_content = re.sub(
        r'CREATE VIEW\s+(\w+)',
        r'CREATE OR REPLACE VIEW \1',
        sql_content,
        flags=re.IGNORECASE
    )
    
    return sql_content

def split_sql_statements(sql_content):
    """
    Split SQL content into individual statements.
    Properly handle dollar-quoted strings ($$) in PostgreSQL functions.
    """
    statements = []
    current_statement = []
    in_dollar_quote = False
    dollar_quote_tag = None
    
    lines = sql_content.split('\n')
    
    for line in lines:
        stripped = line.strip()
        
        # Skip pure comment lines only when not in a function
        if not in_dollar_quote and (not stripped or stripped.startswith('--')):
            continue
        
        # Check for dollar quote markers ($$, $BODY$, etc.)
        dollar_matches = re.findall(r'\$[A-Za-z0-9_]*\$', line)
        for match in dollar_matches:
            if not in_dollar_quote:
                in_dollar_quote = True
                dollar_quote_tag = match
            elif match == dollar_quote_tag:
                in_dollar_quote = False
                dollar_quote_tag = None
        
        current_statement.append(line)
        
        # Check for statement terminator (only when not in dollar quotes)
        if not in_dollar_quote and stripped.endswith(';'):
            statement = '\n'.join(current_statement)
            if statement.strip():
                statements.append(statement)
            current_statement = []
    
    # Add any remaining statement
    if current_statement:
        statement = '\n'.join(current_statement)
        if statement.strip():
            statements.append(statement)
    
    return statements

def execute_sql_file(engine, sql_file_path):
    """Execute SQL file with proper error handling and non-transactional mode."""
    print(f"Reading SQL file: {sql_file_path}")
    
    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")
    
    with open(sql_file_path, 'r') as f:
        sql_content = f.read()
    
    # Modify SQL for idempotency
    sql_content = modify_sql_for_idempotency(sql_content)
    
    # Get existing tables
    existing_tables = get_existing_tables(engine)
    if existing_tables:
        print(f"Existing tables: {', '.join(sorted(existing_tables))}")
    else:
        print("No existing tables found.")
    
    # Split into individual statements
    statements = split_sql_statements(sql_content)
    print(f"\nFound {len(statements)} SQL statements to execute.\n")
    
    executed = 0
    skipped = 0
    errors = 0
    
    # Execute each statement individually (autocommit mode)
    for i, statement in enumerate(statements, 1):
        # Extract statement type for logging
        first_line = statement.strip().split('\n')[0]
        statement_type = ' '.join(first_line.split()[:4])
        if len(statement_type) > 50:
            statement_type = statement_type[:47] + "..."
        
        try:
            print(f"[{i}/{len(statements)}] {statement_type}...", end=' ')
            
            # Execute with autocommit (no transaction)
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(statement))
            
            print("✓")
            executed += 1
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a "already exists" error (safe to skip)
            if any(phrase in error_msg.lower() for phrase in [
                'already exists',
                'duplicate',
                'relation already exists',
                'function already exists'
            ]):
                print("⊘ (already exists)")
                skipped += 1
            else:
                print(f"✗ ERROR")
                print(f"   {error_msg[:200]}")
                errors += 1
    
    print("\n" + "="*60)
    print(f"Migration Summary:")
    print(f"  Executed: {executed}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")
    print("="*60)
    
    if errors > 0:
        print("\n⚠️  Some statements failed. Check the errors above.")
        return False
    else:
        print("\n✓ Schema migration completed successfully!")
        return True

def verify_tables(engine):
    """Verify that critical tables exist."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    required_tables = [
        'verifications',
        'settlements',
        'fee_records',
        'merchant_tiers',
        'idempotency_keys',
        'webhook_deliveries'
    ]
    
    print("\nVerifying critical tables:")
    all_present = True
    for table in required_tables:
        status = "✓" if table in tables else "✗"
        print(f"  {status} {table}")
        if table not in tables:
            all_present = False
    
    return all_present

if __name__ == "__main__":
    print("="*60)
    print("Database Schema Migration Script")
    print("="*60)
    print(f"Database: {DATABASE_URL_SYNC.split('@')[-1]}")
    print()
    
    try:
        engine = create_engine(DATABASE_URL_SYNC, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful\n")
        
        # Execute SQL file
        success = execute_sql_file(engine, SQL_FILE_PATH)
        
        # Verify tables
        if success:
            print()
            if verify_tables(engine):
                print("\n✓ All critical tables verified!")
            else:
                print("\n⚠️  Some critical tables are missing!")
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        raise
    finally:
        engine.dispose()