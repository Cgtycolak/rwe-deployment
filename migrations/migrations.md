# Database Migration History

## Current State
- **Latest Migration**: 20250814000001
- **Migration Chain**:
  1. Base -> dfdfe7849931 (initial_migration)
  2. dfdfe7849931 -> 20240325152900 (add_production_table)
  3. 20240325152900 -> 20240423000000 (add_demand_table)
  4. 20240423000000 -> 20240501000000 (add_forecasting_tables)
  5. 20240501000000 -> 20240612000000 (update_update_id_to_string)
  6. 20240612000000 -> 20250101000000 (add_lignite_tables)
  7. 20250101000000 -> 20250101000001 (add_unlicensed_solar_column)
  8. 20250101000001 -> 20250101000002 (create_unlicensed_solar_table)
  9. 20250101000002 -> 20250101000003 (remove_unlicensed_solar_from_production)
  10. 20250101000003 -> 20250101000004 (create_licensed_solar_table)
  11. 20250101000004 -> 20250813000001 (remove_installed_capacity)
  12. 20250813000001 -> 20250814000001 (remove_updated_at_columns)

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

8. **meteologica_unlicensed_solar** (from 20240501000000, modified by 20240612000000)
   - Created: 2025-05-01
   - Modified: 2025-06-12 (update_id column changed from INTEGER to STRING)
   - Purpose: Store forecasting data for unlicensed solar generation

9. **meteologica_licensed_solar** (from 20240501000000, modified by 20240612000000)
   - Created: 2025-05-01
   - Modified: 2025-06-12 (update_id column changed from INTEGER to STRING)
   - Purpose: Store forecasting data for licensed solar generation

10. **meteologica_wind** (from 20240501000000, modified by 20240612000000)
    - Created: 2025-05-01
    - Modified: 2025-06-12 (update_id column changed from INTEGER to STRING)
    - Purpose: Store forecasting data for wind generation

11. **meteologica_dam_hydro** (from 20240501000000, modified by 20240612000000)
    - Created: 2025-05-01
    - Modified: 2025-06-12 (update_id column changed from INTEGER to STRING)
    - Purpose: Store forecasting data for dam hydro generation

12. **meteologica_runofriver_hydro** (from 20240501000000, modified by 20240612000000)
    - Created: 2025-05-01
    - Modified: 2025-06-12 (update_id column changed from INTEGER to STRING)
    - Purpose: Store forecasting data for run-of-river hydro generation

13. **meteologica_demand** (from 20240501000000, modified by 20240612000000)
    - Created: 2025-05-01
    - Modified: 2025-06-12 (update_id column changed from INTEGER to STRING)
    - Purpose: Store forecasting data for electricity demand

14. **epias_yal** (from 20240501000000)
    - Created: 2025-05-01
    - Purpose: Store system direction data from EPIAS

15. **lignite_heatmap_data** (from 20250101000000)
    - Created: 2025-01-01
    - Purpose: Store lignite plant heatmap data

16. **lignite_realtime_data** (from 20250101000000)
    - Created: 2025-01-01
    - Purpose: Store lignite plant realtime data

17. **unlicensed_solar_data** (from 20250101000002, modified by 20250814000001)
    - Created: 2025-01-01
    - Modified: 2025-08-14 (removed updated_at column)
    - Purpose: Store unlicensed solar data from Meteologica
    - Current Schema:
      - `id`: INTEGER PRIMARY KEY
      - `datetime`: DATETIME NOT NULL UNIQUE
      - `unlicensed_solar`: FLOAT NOT NULL
      - `created_at`: DATETIME

18. **licensed_solar_data** (from 20250101000004, modified by 20250813000001, 20250814000001)
    - Created: 2025-01-01
    - Modified: 2025-08-13 (removed installed_capacity column)
    - Modified: 2025-08-14 (removed updated_at column)
    - Purpose: Store licensed solar data from Meteologica

## How to Verify Current State
```sql
-- Check current migration version
SELECT * FROM alembic_version;
-- Expected output: 20250814000001

-- List all tables
\dt
-- Expected tables:
-- - hydro_heatmap_data
-- - hydro_realtime_data
-- - imported_coal_heatmap_data
-- - natural_gas_heatmap_data
-- - natural_gas_realtime_data
-- - lignite_heatmap_data
-- - lignite_realtime_data
-- - production_data
-- - demand_data
-- - meteologica_unlicensed_solar (schema: meteologica)
-- - meteologica_licensed_solar (schema: meteologica)
-- - meteologica_wind (schema: meteologica)
-- - meteologica_dam_hydro (schema: meteologica)
-- - meteologica_runofriver_hydro (schema: meteologica)
-- - meteologica_demand (schema: meteologica)
-- - epias_yal (schema: epias)
-- - alembic_version
```

## Migration Guidelines
1. Always create new migrations from the latest version (20250814000001)
2. Use meaningful revision IDs (e.g., date_description)
3. Update this document when adding new migrations
4. Test migrations both up and down before committing
5. When removing columns, ensure the application code no longer references them

## Recovery Steps
If migration chain is broken:
```bash
1. Check current version
psql -U rwe_user -d rwe_data -c "SELECT * FROM alembic_version;"

2. Reset to a known good state if needed
psql -U rwe_user -d rwe_data -c "UPDATE alembic_version SET version_num = '20250814000001';"

3. Verify migrations are working
flask db current
flask db history
```

## Emergency Reset
If everything else fails:
```bash
# Drop all tables and start fresh
psql -U rwe_user -d rwe_data
DROP TABLE IF EXISTS production_data CASCADE;
DROP TABLE IF EXISTS demand_data CASCADE;
DROP TABLE IF EXISTS hydro_heatmap_data CASCADE;
DROP TABLE IF EXISTS hydro_realtime_data CASCADE;
DROP TABLE IF EXISTS imported_coal_heatmap_data CASCADE;
DROP TABLE IF EXISTS natural_gas_heatmap_data CASCADE;
DROP TABLE IF EXISTS natural_gas_realtime_data CASCADE;
DROP TABLE IF EXISTS lignite_heatmap_data CASCADE;
DROP TABLE IF EXISTS lignite_realtime_data CASCADE;
DROP TABLE IF EXISTS unlicensed_solar_data CASCADE;
DROP TABLE IF EXISTS licensed_solar_data CASCADE;
DROP SCHEMA IF EXISTS meteologica CASCADE;
DROP SCHEMA IF EXISTS epias CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;
\q

# Rerun all migrations
flask db stamp base
flask db upgrade
```

## Known Issues and Solutions

### Solar Data Update Errors (RESOLVED)
- **Issue**: `column unlicensed_solar_data.updated_at does not exist` error
- **Solution**: Applied migration 20250814000001 to remove problematic columns
- **Status**: ✅ RESOLVED

### Timezone Comparison Errors (RESOLVED)
- **Issue**: "can't compare offset-naive and offset-aware datetimes" in solar update functions
- **Solution**: Updated application code to ensure consistent timezone handling
- **Status**: ✅ RESOLVED

### August 12 Data Showing Zero Values
- **Issue**: Solar data for August 12, 2025 shows all zero values
- **Possible Causes**:
  1. API returning legitimate zero values during low solar generation hours
  2. Missing data from Meteologica API for that specific date
  3. Data processing issues in the update functions
- **Status**:  INVESTIGATING
- **Next Steps**: Add logging to solar update functions to debug data values

## Maintenance Notes
- The solar data tables now have a simplified schema without `updated_at` columns
- All datetime fields should use UTC timezone for consistency
- Solar data updates should now work without database schema errors
- Monitor solar data values to ensure zero values are legitimate (e.g., during night hours)

This document will help:
1. Track the migration history
2. Understand table relationships and current schemas
3. Provide recovery steps
4. Maintain consistent migration practices
5. Document known issues and their resolutions

You should update this document whenever you:
1. Add a new migration
2. Modify table structures
3. Change any migration-related configurations
4. Resolve known issues
5. Add new tables or modify existing ones

Keep it in version control with your code so the whole team can reference it.