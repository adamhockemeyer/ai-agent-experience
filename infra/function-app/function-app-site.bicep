@description('Azure region where resources should be deployed')
param location string

@description('Name of the function app')
param name string

@description('Resource ID of the app service plan to use for the function app')
param appServicePlanId string

@description('Runtime stack for the function app')
param runtime string = 'python'

@description('Runtime version for the function app')
param runtimeVersion string = '3.10'

@description('Tags for all resources')
param tags object = {}

@description('Identity type for the function app - can be None, SystemAssigned, or UserAssigned')
@allowed([
  'None'
  'SystemAssigned'
  'UserAssigned'
])
param identityType string = 'SystemAssigned'

@description('ID of the user-assigned managed identity - required when identityType is UserAssigned')
param identityId string = ''

param principalId string = ''

@description('Environment variables for the function app')
param env array = []

@description('Connection string for Application Insights')
param applicationInsightsConnectionString string = ''

@description('Storage account name for function app')
param storageAccountName string = ''

@description('Maximum number of instances for the function app')
param maximumInstanceCount int = 100

@description('Memory allocated per instance in MB')
param instanceMemoryMB int = 2048

@description('Storage container name for function app deployment')
param deploymentStorageContainerName string = 'function-releases'

// Create identity configuration based on the identity type
var identityConfig = identityType == 'UserAssigned'
  ? {
      type: 'UserAssigned'
      userAssignedIdentities: {
        '${identityId}': {}
      }
    }
  : identityType == 'SystemAssigned'
      ? {
          type: 'SystemAssigned'
        }
      : {
          type: 'None'
        }

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = if (!empty(storageAccountName)) {
  name: storageAccountName
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: identityConfig
  properties: {
    serverFarmId: appServicePlanId
    siteConfig: {
      appSettings: concat(
        [
          !empty(storageAccountName)
            ? {
                name: 'AzureWebJobsStorage__accountName'
                value: storageAccountName
              }
            : null
          !empty(applicationInsightsConnectionString)
            ? {
                name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
                value: applicationInsightsConnectionString
              }
            : null
        ],
        env
      )
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: !empty(storageAccountName)
            ? '${storageAccount.properties.primaryEndpoints.blob}${deploymentStorageContainerName}'
            : ''
          authentication: identityType == 'UserAssigned'
            ? {
                type: 'UserAssignedIdentity'
                userAssignedIdentityResourceId: identityId
              }
            : identityType == 'SystemAssigned'
              ? {
                  type: 'SystemAssignedIdentity'
                }
              : {
                  type: 'None'
                }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: maximumInstanceCount
        instanceMemoryMB: instanceMemoryMB
      }
      runtime: {
        name: runtime == 'python' ? 'python' : 'dotnet-isolated'
        version: runtime == 'python' ? runtimeVersion : '8.0'
      }
    }
    httpsOnly: true
  }
}

// Add Storage Blob Data Owner role assignment if using managed identity
var storageRoleDefinitionId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b' // Storage Blob Data Owner role

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = if (!empty(storageAccountName) && identityType != 'None') {
  name: guid(resourceId('Microsoft.Storage/storageAccounts', storageAccountName), storageRoleDefinitionId, name)
  scope: storageAccount
  properties: {
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', storageRoleDefinitionId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

@description('Resource ID of the function app')
output resourceId string = functionApp.id

@description('Name of the function app')
output name string = functionApp.name

@description('Default hostname of the function app')
output defaultHostname string = functionApp.properties.defaultHostName

@description('Principal ID of the function app managed identity')
output principalId string = identityType != 'None' ? principalId : ''
