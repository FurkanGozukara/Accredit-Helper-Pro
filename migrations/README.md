# Database Migrations

This directory contains migration scripts for database schema changes and optimizations.

## Available Migrations

### 1. Add Indexes (`add_indexes.py`)

This migration adds indexes to existing tables to improve query performance. It's safe to run on an existing database with data.

**Usage:**
```bash
python migrations/add_indexes.py
```

### 2. Update Schema (`update_schema.py`)

This migration updates the database schema to include index definitions in the tables. **WARNING: This will drop all tables and recreate them, resulting in data loss.**

Only use this if:
- You have a fresh installation with no important data
- You have backed up your database first

**Usage:**
```bash
python migrations/update_schema.py
```

## Recommended Approach

For existing databases with data:

1. Backup your database first
   ```bash
   # Use the utility route for backup or make a manual copy of your SQLite file
   ```

2. Run the `add_indexes.py` script to add indexes to your existing database
   ```bash
   python migrations/add_indexes.py
   ```

For new installations:

1. Just run the application normally, as the models now include index definitions

## Troubleshooting

If you encounter any issues with these migrations:

1. Restore from your backup
2. Check the error message for any syntax issues or conflicting index names
3. Try running each index creation statement individually 