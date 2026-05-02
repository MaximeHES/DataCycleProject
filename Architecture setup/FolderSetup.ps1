# ==========================================
# Data Cycle - Folder Structure Creation
# ==========================================

Write-Host "Creating Data Cycle folder structure..." -ForegroundColor Cyan

# ==========================================
# ROOT FOLDERS
# ==========================================

$folders = @(
    "C:\RawData\Eversys",
    "C:\RawData\Eversys\Product_History",
    "C:\RawData\Eversys\Cleaning_History",
    "C:\RawData\Eversys\Rinse_History",
    "C:\RawData\Eversys\Info_Message_History",

    "C:\RawData\Eversys_Cleaned",
    "C:\RawData\Eversys_Cleaned\Product_History",
    "C:\RawData\Eversys_Cleaned\Cleaning_History",
    "C:\RawData\Eversys_Cleaned\Rinse_History",
    "C:\RawData\Eversys_Cleaned\Info_Message_History",

    "C:\DeployBackup_CICD_Test",
    "C:\DataCycle_CICD_Test"
)

# ==========================================
# CREATE FOLDERS
# ==========================================

foreach ($folder in $folders) {

    if (!(Test-Path $folder)) {

        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "Created: $folder" -ForegroundColor Green

    }
    else {

        Write-Host "Already exists: $folder" -ForegroundColor Yellow

    }
}

Write-Host ""
Write-Host "Folder structure creation completed." -ForegroundColor Cyan