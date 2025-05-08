param(
    [Parameter()]
    [string]$storage_account_name,
    
    [Parameter()]
    [string]$search_service_name,
    
    [Parameter()]
    [string]$openai_endpoint,
    
    [Parameter()]
    [string]$blob_container_name = "documents",
    
    [Parameter()]
    [string]$embedding_deployment_name = "embedding",
    
    [Parameter()]
    [switch]$wait_for_indexer
)

Write-Host "Setting up Azure AI Search indexes for document folders..."

# If parameters are not provided, try to get them from AZD environment
if (-not $storage_account_name) {
    # Ensure we strip any quotes from the value
    $storage_account_name = $(azd env get-values --no-prompt | Select-String -Pattern "AZURE_STORAGE_ACCOUNT_NAME=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim('"').Trim("'") })
}

if (-not $search_service_name) {
    # Try multiple possible environment variable names
    $search_service_name = $(azd env get-values --no-prompt | Select-String -Pattern "AZURE_SEARCH_SERVICE_NAME=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim('"').Trim("'") })
    if (-not $search_service_name) {
        $search_service_name = $(azd env get-values --no-prompt | Select-String -Pattern "AI_AGENTS_SEARCH_NAME=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim('"').Trim("'") })
    }
    if (-not $search_service_name) {
        $search_service_name = $(azd env get-values --no-prompt | Select-String -Pattern "AI_SEARCH_SERVICE=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim('"').Trim("'") })
    }
}

if (-not $openai_endpoint) {
    # Try to get full endpoint first
    $openai_endpoint = $(azd env get-values --no-prompt | Select-String -Pattern "AZURE_OPENAI_ENDPOINT=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim('"').Trim("'") })
    
    if (-not $openai_endpoint) {
        # Fall back to constructing from service name
        $openai_service_name = $(azd env get-values --no-prompt | Select-String -Pattern "AZURE_OPENAI_SERVICE_NAME=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim('"').Trim("'") })
        if ($openai_service_name) {
            $openai_endpoint = "https://$openai_service_name.openai.azure.com/"
        }
    }
}

# Check if embedding deployment name is in environment
$env_embedding_name = $(azd env get-values --no-prompt | Select-String -Pattern "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=(.+)" | ForEach-Object { $_.Matches.Groups[1].Value.Trim('"').Trim("'") })
if ($env_embedding_name) {
    $embedding_deployment_name = $env_embedding_name
}

# Output without quotes by using Write-Host
Write-Host "Using Storage Account: $storage_account_name"
Write-Host "Using Search Service: $search_service_name"
Write-Host "Using OpenAI Endpoint: $openai_endpoint"
Write-Host "Using Blob Container: $blob_container_name"
Write-Host "Using Embedding Deployment: $embedding_deployment_name"

# Set up environment variables for the Python scripts
$env:AZURE_SEARCH_SERVICE_NAME = $search_service_name
$env:AZURE_STORAGE_ACCOUNT_NAME = $storage_account_name
$env:AZURE_OPENAI_ENDPOINT = $openai_endpoint
$env:BLOB_CONTAINER_NAME = $blob_container_name
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = $embedding_deployment_name

# Path to search setup scripts
$searchSetupPath = Join-Path $PSScriptRoot "search_setup"

# Install dependencies
Write-Host "Installing dependencies for search setup..."
pip install -r "$searchSetupPath/requirements.txt"

# Run the search setup script
Write-Host "Running search setup..."
$waitTime = if ($wait_for_indexer) { 60 } else { 0 }
python "$searchSetupPath/main.py" --wait $waitTime

Write-Host "Search index setup completed!"