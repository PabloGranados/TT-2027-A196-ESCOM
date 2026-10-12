# Restaura un respaldo SQL en el contenedor escom_db
# Uso: .\scripts\restore_db.ps1 -File .\backups\hardware_match_YYYYMMDD_HHMMSS.sql
param([Parameter(Mandatory = $true)][string]$File)
docker exec escom_db psql -U escom_user -d postgres -c "DROP DATABASE IF EXISTS hardware_match_db;"
docker exec escom_db psql -U escom_user -d postgres -c "CREATE DATABASE hardware_match_db;"
Get-Content $File -Raw | docker exec -i escom_db psql -U escom_user -d hardware_match_db
Write-Host "Restauración completa."
