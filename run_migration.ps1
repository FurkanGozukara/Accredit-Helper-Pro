# Run the migration script to add achievement levels
Write-Host "Running migration to add achievement levels table..." -ForegroundColor Cyan

# Activate the virtual environment
. .\venv\Scripts\Activate.ps1

# Run the migration script
python -c "from app import create_app; from migrations.add_achievement_levels import upgrade; app = create_app(); app.app_context().push(); upgrade()"

# Deactivate the virtual environment
deactivate

Write-Host "Migration completed." -ForegroundColor Green 