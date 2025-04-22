# Database Migration History

## Current State
- **Latest Migration**: 20240423000000
- **Migration Chain**:
  1. Base -> dfdfe7849931 (initial_migration)
  2. dfdfe7849931 -> 20240325152900 (add_production_table)
  3. 20240325152900 -> 20240423000000 (add_demand_table)

## Tables
1. **hydro_heatmap_data** (from dfdfe7849931)
   - Created: 2025-03-11
   - Purpose: Store hydro plant heatmap data

2. **hydro_realtime_data** (from dfdfe7849931)
   - Created: 2025-03-11
   - Purpose: Store hydro plant realtime data

3. **imported_coal_heatmap_data** (from dfdfe7849931)
   - Created: 2025-03-11
   - Purpose: Store imported coal plant heatmap data

4. **natural_gas_heatmap_data** (from dfdfe7849931)
   - Created: 2025-03-11
   - Purpose: Store natural gas plant heatmap data

5. **natural_gas_realtime_data** (from dfdfe7849931)
   - Created: 2025-03-11
   - Purpose: Store natural gas plant realtime data

6. **production_data** (from 20240325152900)
   - Created: 2025-03-25
   - Purpose: Store aggregated production data for all energy types

7. **demand_data** (from 20240423000000)
   - Created: 2025-04-23
   - Purpose: Store electricity demand data

## How to Verify Current State
sql
-- Check current migration version
SELECT FROM alembic_version;
-- Expected output: 20240325152900
-- List all tables
\dt
-- Expected tables:
-- - hydro_heatmap_data
-- - hydro_realtime_data
-- - imported_coal_heatmap_data
-- - natural_gas_heatmap_data
-- - natural_gas_realtime_data
-- - production_data
-- - alembic_version


## Migration Guidelines
1. Always create new migrations from the latest version
2. Use meaningful revision IDs (e.g., date_description)
3. Update this document when adding new migrations
4. Test migrations both up and down before committing

## Recovery Steps
If migration chain is broken:
bash
1. Check current version
psql -U rwe_user -d rwe_data -c "SELECT FROM alembic_version;"
2. Reset to a known good state if needed
psql -U rwe_user -d rwe_data -c "UPDATE alembic_version SET version_num = '20240325152900';"
3. Verify migrations are working
flask db current
flask db history

## Emergency Reset
If everything else fails:
bash
Drop all tables and start fresh
psql -U rwe_user -d rwe_data
DROP TABLE IF EXISTS production_data CASCADE;
DROP TABLE IF EXISTS hydro_heatmap_data CASCADE;
DROP TABLE IF EXISTS hydro_realtime_data CASCADE;
DROP TABLE IF EXISTS imported_coal_heatmap_data CASCADE;
DROP TABLE IF EXISTS natural_gas_heatmap_data CASCADE;
DROP TABLE IF EXISTS natural_gas_realtime_data CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;
\q
Rerun all migrations
flask db stamp base
flask db upgrade
```


This document will help:
1. Track the migration history
2. Understand table relationships
3. Provide recovery steps
4. Maintain consistent migration practices

You should update this document whenever you:
1. Add a new migration
2. Modify table structures
3. Change any migration-related configurations

Keep it in version control with your code so the whole team can reference it.