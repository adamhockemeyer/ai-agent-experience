param(
    [Parameter(Mandatory = $true)]
    [string]$storage_account_name,
    [Parameter(Mandatory = $false)]
    [string]$storage_account_key,
    [Parameter(Mandatory = $false)]
    [string]$blob_container_name = "documents",
    [Parameter(Mandatory = $false)]
    [string]$local_documents_path = ".\documents"
)

function Write-Info { param([string]$m) Write-Host "ℹ️  $m" -ForegroundColor Cyan }
function Write-Act { param([string]$m) Write-Host "➡️  $m" -ForegroundColor Yellow }
function Write-Warn { param([string]$m) Write-Host "⚠️  $m" -ForegroundColor DarkYellow }
function Write-Ok { param([string]$m) Write-Host "✅ $m" -ForegroundColor Green }

if (-not (Test-Path $local_documents_path)) { Write-Warn "Local path '$local_documents_path' does not exist. Skipping."; exit 0 }
if (-not $storage_account_key) {
    Write-Info "Retrieving storage account key..."
    $storage_account_key = az storage account keys list --account-name $storage_account_name --query "[0].value" -o tsv
}

Write-Act "Ensuring container '$blob_container_name' exists"
az storage container create --name $blob_container_name --account-name $storage_account_name --account-key $storage_account_key --output none | Out-Null

# Fast path: AzCopy sync if available
$azcopy = Get-Command azcopy -ErrorAction SilentlyContinue
if ($azcopy) {
    Write-Info "AzCopy detected at $($azcopy.Source); attempting incremental sync (no delete)."
    try {
        $expiry = (Get-Date).AddHours(1).ToString('yyyy-MM-ddTHH:mm:ssZ')
        $sas = az storage container generate-sas --name $blob_container_name --account-name $storage_account_name --account-key $storage_account_key --permissions rlwacd --expiry $expiry -o tsv
        if ($sas) {
            $dest = "https://${storage_account_name}.blob.core.windows.net/${blob_container_name}?$sas"
            Write-Act "Running azcopy sync ..."
            $syncOut = azcopy sync $local_documents_path $dest --recursive --delete-destination=false --overwrite=ifSourceNewer 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "AzCopy sync completed."
                return
            }
            else {
                Write-Warn "AzCopy sync failed (exit $LASTEXITCODE). Falling back. Details: $syncOut"
            }
        }
        else {
            Write-Warn "Failed to generate SAS for AzCopy; falling back to per-file uploads."
        }
    }
    catch {
        Write-Warn "AzCopy path encountered exception: $_ . Falling back."
    }
}
else {
    Write-Info "AzCopy not found; using per-file upload logic."
}

Write-Info "Listing existing blobs (fallback mode)..."
$existingBlobs = az storage blob list --container-name $blob_container_name --account-name $storage_account_name --account-key $storage_account_key --query "[].name" -o tsv
$existingSet = @{}
foreach ($b in $existingBlobs) { if ($b) { $existingSet[$b] = $true } }
Write-Info "Found $($existingSet.Keys.Count) existing blobs"

$files = Get-ChildItem -Path $local_documents_path -File -Recurse
$uploaded = 0
$skipped = 0
foreach ($file in $files) {
    try {
        $basePath = (Resolve-Path $local_documents_path).Path
        if (-not $basePath.EndsWith('\\')) { $basePath = "$basePath\" }
        $full = $file.FullName
        $relative = if ($full.StartsWith($basePath, [System.StringComparison]::OrdinalIgnoreCase)) { $full.Substring($basePath.Length) } else { $file.Name }
        $relative = $relative -replace "^[/\\]+", "" -replace "\\", "/"
        if ([string]::IsNullOrWhiteSpace($relative)) { Write-Warn "Derived empty relative path for '$($file.FullName)'"; continue }
        if ($existingSet.ContainsKey($relative)) { Write-Info "Skip (exists): $relative"; $skipped++; continue }
        Write-Act "Uploading: $relative"
        $uploadResult = az storage blob upload --account-name $storage_account_name --account-key $storage_account_key --container-name $blob_container_name --name $relative --file $file.FullName --overwrite false --no-progress -o none 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Warn "Upload failed for ${relative}: $uploadResult" } else { $uploaded++ }
    }
    catch { Write-Warn "Exception processing '$($file.FullName)': $_" }
}

Write-Ok "Completed (fallback). Uploaded: $uploaded, Skipped existing: $skipped"
