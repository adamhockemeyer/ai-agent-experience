#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sets up Event Grid system topic and subscription for blob storage events to Azure Functions
.DESCRIPTION
    This script discovers existing Event Grid system topics, creates new ones if needed,
    and sets up event subscriptions to trigger Azure Functions on blob storage events.
.PARAMETER StorageAccountName
    Name of the Azure Storage Account
.PARAMETER ResourceGroupName
    Name of the Azure Resource Group
.PARAMETER FunctionAppName
    Name of the Azure Function App
.PARAMETER EnvironmentName
    Name of the azd environment (prefix)
.PARAMETER Location
    Azure location/region
.EXAMPLE
    .\setup-event-grid.ps1 -StorageAccountName "mystorage" -ResourceGroupName "myrg" -FunctionAppName "myfunc" -EnvironmentName "dev" -Location "eastus2"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$StorageAccountName,
    
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory = $true)]
    [string]$FunctionAppName,
    
    [Parameter(Mandatory = $true)]
    [string]$EnvironmentName,
    
    [Parameter(Mandatory = $true)]
    [string]$Location
)

try {
    # Allow external override of naming prefix to stay consistent with main deployment
    $ResolvedPrefix = if ($env:EVENTGRID_RESOURCE_PREFIX) { $env:EVENTGRID_RESOURCE_PREFIX } else { $EnvironmentName }
    Write-Host "=== Event Grid System Topic Setup ===" -ForegroundColor Cyan
    
    # Get required values from Azure with error checking
    Write-Host "Retrieving storage account information..." -ForegroundColor Yellow
    $storageId = az resource show --name $StorageAccountName --resource-group $ResourceGroupName --resource-type "Microsoft.Storage/storageAccounts" --query id -o tsv
    if (-not $storageId) {
        throw "Failed to retrieve storage account ID for '$StorageAccountName'"
    }
    
    Write-Host "Retrieving function app resource ID..." -ForegroundColor Yellow
    $functionAppId = az functionapp show --name $FunctionAppName --resource-group $ResourceGroupName --query id -o tsv
    if (-not $functionAppId) {
        throw "Failed to retrieve function app ID for '$FunctionAppName'"
    }
    
    # Construct function resource ID for Event Grid subscription
    # Event Grid requires the full function path: /subscriptions/.../Microsoft.Web/sites/{functionapp}/functions/{functionname}
    $mcpFunctionResourceId = "$functionAppId/functions/event_grid_blob_trigger"
    
    Write-Host "Storage Account ID: $storageId" -ForegroundColor Green
    Write-Host "Function Resource ID: $mcpFunctionResourceId" -ForegroundColor Green
    
    # Verify the function exists before proceeding
    Write-Host "Verifying function exists..." -ForegroundColor Yellow
    $availableFunctions = az functionapp function list --name $FunctionAppName --resource-group $ResourceGroupName --query "[].name" -o tsv
    
    # Check if our target function exists (with or without function app prefix)
    $targetFunctionName = "event_grid_blob_trigger"
    $functionExists = $false
    $actualFunctionName = $null
    
    if ($availableFunctions) {
        foreach ($func in $availableFunctions) {
            if ($func -eq $targetFunctionName -or $func -like "*/$targetFunctionName") {
                $functionExists = $true
                $actualFunctionName = if ($func -like "*/*") { $func.Split('/')[-1] } else { $func }
                Write-Host "✅ Found function: $func" -ForegroundColor Green
                break
            }
        }
    }
    
    if (-not $functionExists) {
        Write-Warning "⚠️ Function '$targetFunctionName' not found in function app '$FunctionAppName'"
        Write-Host "Available functions:" -ForegroundColor Yellow
        if ($availableFunctions) {
            $availableFunctions | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
        }
        else {
            Write-Host "  No functions found in function app" -ForegroundColor Gray
        }
        throw "Function '$targetFunctionName' must exist before creating Event Grid subscription"
    }
    else {
        Write-Host "✅ Function '$targetFunctionName' confirmed to exist" -ForegroundColor Green
    }
    
    # Discovery phase - check for existing system topics
    Write-Host "Checking for existing Event Grid system topics..." -ForegroundColor Yellow
    $allTopics = az eventgrid system-topic list --resource-group $ResourceGroupName -o json | ConvertFrom-Json
    
    # Filter topics that match our storage account (case-insensitive comparison)
    $existingTopics = @()
    foreach ($topic in $allTopics) {
        Write-Host "Checking topic: $($topic.name)" -ForegroundColor Gray
        
        # Check different possible source locations (Azure CLI structure varies)
        $sourceValue = $null
        if ($topic.properties -and $topic.properties.source) {
            $sourceValue = $topic.properties.source
            Write-Host "  📍 Found source in properties.source" -ForegroundColor DarkGray
        }
        elseif ($topic.source) {
            $sourceValue = $topic.source
            Write-Host "  📍 Found source in topic.source" -ForegroundColor DarkGray
        }
        else {
            Write-Host "  ⚠️  Skipping - no source property found" -ForegroundColor Yellow
            continue
        }
        
        # Normalize both URLs to lowercase for comparison
        $topicSource = $sourceValue.ToLower()
        $targetSource = $storageId.ToLower()
        
        # Also handle the resource path differences (microsoft.storage vs Microsoft.Storage)
        $normalizedTopicSource = $topicSource -replace "microsoft\.storage\.storageaccounts", "microsoft.storage/storageaccounts"
        $normalizedTargetSource = $targetSource -replace "microsoft\.storage\.storageaccounts", "microsoft.storage/storageaccounts"
        
        if ($normalizedTopicSource -eq $normalizedTargetSource) {
            Write-Host "✅ Found matching system topic: $($topic.name)" -ForegroundColor Green
            $existingTopics += [PSCustomObject]@{
                name              = $topic.name
                id                = $topic.id
                provisioningState = if ($topic.properties) { $topic.properties.provisioningState } else { $topic.provisioningState }
                source            = $sourceValue
            }
        }
        else {
            Write-Host "  ❌ No match: $topicSource vs $targetSource" -ForegroundColor DarkGray
        }
    }
    
    $deploymentParams = @(
        "prefix=$ResolvedPrefix"
        "location=$Location"
        "storageAccountId=$storageId"
        "mcpFunctionResourceId=$mcpFunctionResourceId"
        "deadLetterStorageAccountId=$storageId"
    )
    
    if ($existingTopics.Count -gt 0) {
        $existingTopicName = $existingTopics[0].name
        Write-Host "✅ Found existing system topic: $existingTopicName" -ForegroundColor Green
        Write-Host "Will use existing system topic for Event Grid subscription" -ForegroundColor Cyan
        $deploymentParams += "existingSystemTopicName=$existingTopicName"
        
        # Check for existing subscriptions that might conflict
        $existingSubscriptions = az eventgrid system-topic event-subscription list --resource-group $ResourceGroupName --system-topic-name $existingTopicName --query "[].name" -o tsv
        if ($existingSubscriptions) {
            Write-Warning "Existing event subscriptions found: $($existingSubscriptions -join ', ')"
            Write-Warning "Please verify these don't conflict with the new subscription"
        }
    }
    else {
        Write-Host "✅ No existing system topic found - will create new one" -ForegroundColor Green
    }
    
    # Deploy Event Grid resources using native Bicep template
    Write-Host "Deploying Event Grid resources with native Bicep template..." -ForegroundColor Yellow
    Write-Host "Parameters:" -ForegroundColor Gray
    $deploymentParams | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    
    $deploymentResult = az deployment group create `
        --resource-group $ResourceGroupName `
        --template-file "infra/event-grid-native.bicep" `
        --parameters $deploymentParams `
        --output json | ConvertFrom-Json
    
    if ($LASTEXITCODE -ne 0) {
        throw "Event Grid deployment failed with exit code $LASTEXITCODE"
    }
    
    # Display results
    $outputs = $deploymentResult.properties.outputs
    Write-Host "✅ Event Grid deployment completed successfully!" -ForegroundColor Green
    Write-Host "📊 Deployment Summary:" -ForegroundColor Cyan
    Write-Host "  - System Topic: $($outputs.systemTopicName.value)" -ForegroundColor White
    Write-Host "  - Subscription: $($outputs.subscriptionName.value)" -ForegroundColor White
    Write-Host "  - Using Existing Topic: $($outputs.isUsingExistingTopic.value)" -ForegroundColor White
    
    # Verify the deployment by checking subscription status
    Write-Host "Verifying Event Grid subscription..." -ForegroundColor Yellow
    $subscriptionStatus = az eventgrid system-topic event-subscription show `
        --name $outputs.subscriptionName.value `
        --resource-group $ResourceGroupName `
        --system-topic-name $outputs.systemTopicName.value `
        --query "provisioningState" -o tsv
    
    if ($subscriptionStatus -eq "Succeeded") {
        Write-Host "✅ Event Grid subscription is active and ready" -ForegroundColor Green
    }
    else {
        Write-Warning "⚠️ Event Grid subscription status: $subscriptionStatus"
    }
    
    Write-Host "🎉 Event Grid setup completed successfully!" -ForegroundColor Green
}
catch {
    Write-Error "❌ Event Grid setup failed: $_"
    Write-Host "💡 Troubleshooting tips:" -ForegroundColor Yellow
    Write-Host "  1. Check if system topic already exists: .\scripts\discover-system-topics.ps1 -StorageAccountName '$StorageAccountName' -ResourceGroupName '$ResourceGroupName'" -ForegroundColor Gray
    Write-Host "  2. Verify function app is deployed and ready" -ForegroundColor Gray
    Write-Host "  3. Check Azure permissions for Event Grid operations" -ForegroundColor Gray
    Write-Host "  4. Ensure function 'event_grid_blob_trigger' exists in the function app" -ForegroundColor Gray
    exit 1
}
