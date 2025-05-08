param(
    [Parameter(Mandatory = $false)]
    [Alias("a")]
    [string]$storage_account_name,

    [Parameter(Mandatory = $false)]
    [Alias("k")]
    [string]$storage_account_key,

    [Parameter(Mandatory = $false)]
    [Alias("c")]
    [string]$blob_container_name = "documents",

    [Parameter(Mandatory = $false)]
    [Alias("p")]
    [string]$local_documents_path = ".\documents"
)

function Write-Status {
    param([string]$Message, [string]$Emoji = "ℹ️")
    Write-Host "$Emoji $Message"
}

Write-Status "🔑 Loading parameters"

# Print resolved values for debugging
Write-Status "Using storage_account_name: $storage_account_name"
Write-Status "Using blob_container_name: $blob_container_name"
Write-Status "Using local_documents_path: $local_documents_path"

# Check for required values
if (-not $storage_account_name) {
    Write-Status "❌ storage_account_name is not set. Please provide it using -a or -storage_account_name parameter." "❌"
    exit 1
}
if (-not (Test-Path $local_documents_path)) {
    Write-Status "❌ Local documents folder '$local_documents_path' does not exist." "❌"
    exit 1
}

if (-not $storage_account_key) {
    Write-Status "🔍 No storage account key provided, retrieving with az storage account keys list"
    $storage_account_key = az storage account keys list `
        --account-name $storage_account_name `
        --query "[0].value" `
        -o tsv
}

Write-Status "📦 Creating blob container '$blob_container_name' if it doesn't exist..." "📦"
az storage container create `
    --name $blob_container_name `
    --account-name $storage_account_name `
    --account-key $storage_account_key `
    --output none

# Count local files
$localFiles = Get-ChildItem -Path $local_documents_path -Recurse -File
$localFileCount = $localFiles.Count
Write-Status "📂 Found $localFileCount files in $local_documents_path to upload." "📂"

Write-Status "⬆️  Uploading files to the storage account container..." "⬆️"
az storage blob upload-batch `
    --account-name $storage_account_name `
    --account-key $storage_account_key `
    --destination $blob_container_name `
    --source $local_documents_path `
    --overwrite

# Count blobs in the container after upload
$blobList = az storage blob list `
    --container-name $blob_container_name `
    --account-name $storage_account_name `
    --account-key $storage_account_key `
    --query "[].name" `
    -o tsv
$blobCount = ($blobList | Measure-Object -Line).Lines

Write-Status "✅ Upload complete. $localFileCount files in source, $blobCount blobs in container." "✅"
if ($localFileCount -ne $blobCount) {
    Write-Status "⚠️  Warning: Source file count and blob count do not match!" "⚠️"
}
