Seed files and import instructions

Use these sample JSON files to populate a local `SmartHome_DB` for development and testing.

Prerequisites
- MongoDB running locally or reachable via URI
- MongoDB Database Tools (mongoimport) installed
- Python with packages: `pymongo`, `python-dateutil` (for migration script)

Backup your DB before importing:
```bash
mongodump --uri="mongodb://localhost:27017/SmartHome_DB" --out=backup_$(date +%Y%m%d)
```

Import seed files (run from repo root `smart-house`):
```bash
# sensor data
mongoimport --uri="mongodb://localhost:27017/SmartHome_DB" --collection=sensor_data --file="seeds/sensor_data_seed.json" --jsonArray

# devices
mongoimport --uri="mongodb://localhost:27017/SmartHome_DB" --collection=devices --file="seeds/devices_seed.json" --jsonArray

# automation rules
mongoimport --uri="mongodb://localhost:27017/SmartHome_DB" --collection=automation_rules --file="seeds/automation_rules_seed.json" --jsonArray

# users
mongoimport --uri="mongodb://localhost:27017/SmartHome_DB" --collection=users --file="seeds/users_seed.json" --jsonArray

# alert history
mongoimport --uri="mongodb://localhost:27017/SmartHome_DB" --collection=alert_history --file="seeds/alert_history_seed.json" --jsonArray
```

Notes
- Seed `timestamp` fields use MongoDB Extended JSON (`{"$date":"..."}`) and will be imported as proper `Date` values.
- After import run the migration to ensure indexes and added fields:
```bash
pip install pymongo python-dateutil
python migrations/migrate_db.py --uri "mongodb://localhost:27017" --db SmartHome_DB
```
- If you prefer a dry-run preview, copy the files and inspect them or run the migration script in a development sandbox first.
