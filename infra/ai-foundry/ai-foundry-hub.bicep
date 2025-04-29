@description('The location into which the Azure AI resources should be deployed.')
param location string

@description('Name of the AI Foundry Hub resource')
param name string

@description('Tags to be applied to all deployed resources')
param tags object = {}

@description('Application Insights ID where data will be sent')
param applicationInsightsId string

@description('Storage account ID to be used by the AI Foundry Project')
param storageAccountId string

@description('AI Service Account kind: either OpenAI or AIServices')
param aiServiceKind string

@description('Name AI Services resource')
param aiServicesName string

@description('Resource ID of the AI Services endpoint')
param aiServicesTarget string

@description('Resource ID of the AI Services resource')
param aiServicesId string

@description('Name AI Search resource')
param aiSearchName string

@description('Resource ID of the AI Search resource')
param aiSearchId string

@description('Optional deployment settings for models')
param aoaiModelDeployments array = []

@description('Role assignments')
param roleAssignments array = []

param skuName string = 'Basic'
param skuTier string = 'Basic'

var aoaiConnection = '${name}-connection-AIServices_aoai'

var kindAIServicesExists = aiServiceKind == 'AIServices'

var aiServiceConnectionName = kindAIServicesExists ? '${name}-connection-AIServices' : aoaiConnection

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: aiServicesName
}

resource aiSearch 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: aiSearchName
}

resource foundryHub 'Microsoft.MachineLearningServices/workspaces@2025-01-01-preview' = {
  name: name
  location: location
  sku: {
    name: skuName
    tier: skuTier
  }
  // @description('The SKU of the AI Foundry Hub resource')
  kind: 'hub'
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: name
    applicationInsights: applicationInsightsId
    storageAccount: storageAccountId
    // keyVault:
    publicNetworkAccess: 'Enabled'
  }
}

resource connection_aisvc 'Microsoft.MachineLearningServices/workspaces/connections@2025-01-01-preview' = {
  name: aiServiceConnectionName
  parent: foundryHub
  properties: {
    category: aiServiceKind // either AIServices or AzureOpenAI
    target: aiServicesTarget
    useWorkspaceManagedIdentity: true
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiServicesId
      location: aiServices.location
    }
  }
}

resource connection_search 'Microsoft.MachineLearningServices/workspaces/connections@2025-01-01-preview' = {
  name: '${name}-connection-search'
  parent: foundryHub
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${aiSearchName}.search.windows.net/'
    // useWorkspaceManagedIdentity: true
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiSearchId
      location: aiSearch.location
    }
  }
}

resource capabilityHosts_Agent 'Microsoft.MachineLearningServices/workspaces/capabilityHosts@2025-01-01-preview' = {
  parent: foundryHub
  name: '${name}-capabilityHosts-Agent'
  properties: {
    capabilityHostKind: 'Agents'
  }
}

@description('This module assigns the specified role to the AI Foundry Hub resource')
module roleAssignment '../auth/role-assignment.bicep' = [
  for (roleAssignment, i) in roleAssignments: {
    name: '${name}-hub-role-assignment-${i}'
    params: {
      principalId: roleAssignment.principalId
      roleDefinitionId: roleAssignment.roleDefinitionId
    }
  }
]

output id string = foundryHub.id
output name string = foundryHub.name
output principalId string = foundryHub.identity.principalId
output connection_aisvcId string = connection_aisvc.id
output connection_searchId string = connection_search.id
output connection_aisvcName string = connection_aisvc.name
output connection_searchName string = connection_search.name
