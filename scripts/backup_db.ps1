# Respaldo de la base de datos PostgreSQL (contenedor escom_db)
# Uso: .\scripts\backup_db.ps1
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force "$PSScriptRoot\..\backups" | Out-Null
$out = "$PSScriptRoot\..\backups\hardware_match_$stamp.sql"
docker exec escom_db pg_dump -U escom_user -d hardware_match_db --no-owner | Out-File -Encoding utf8 $out
Write-Host "Respaldo creado en $out"
