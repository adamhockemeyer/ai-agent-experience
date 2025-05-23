@description('The location into which the Azure AI resources should be deployed.')
param location string = resourceGroup().location

@description('Name of the AI Foundry Project resource')
param name string

@description('Tags to be applied to all deployed resources')
param tags object = {}

@description('The ID of the AI Foundry Hub to associate with this project.')
param hubId string

@description('Name of the AI Foundry Hub resource')
param hubName string

@description('Role assignments for the AI Foundry Project')
param roleAssignments array = []

param aiServicesConnectionName array = []

@description('Optional deployment settings for models')
param modelDeployments array = []

resource hub 'Microsoft.MachineLearningServices/workspaces@2025-01-01-preview' existing = {
  name: hubName
}

resource foundryProject 'Microsoft.MachineLearningServices/workspaces@2025-01-01-preview' = {
  name: name
  location: location
  kind: 'project'
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: name
    hubResourceId: hubId

    // primaryUserAssignedIdentity: null
    // applicationInsights: null // Inherited from hub
    //storageAccount: storageAccountId
    publicNetworkAccess: 'Enabled'
  }
}

// resource capabilityHosts_Agent 'Microsoft.MachineLearningServices/workspaces/capabilityHosts@2025-01-01-preview' = {
//   parent: foundryProject
//   name: '${name}-capabilityHosts-Agent'
//   properties: {
//     capabilityHostKind: 'Agents'
//     aiServicesConnections: aiServicesConnectionName
//   }
//   dependsOn: [
//     hub
//   ]
// }

// @description('This module assigns the specified role to the AI Foundry Project resource')
// module roleAssignment '../auth/role-assignment.bicep' = [
//   for (roleAssignment, i) in roleAssignments: {
//     name: '${name}-project-role-assignment-${i}'
//     params: {
//       principalId: roleAssignment.principalId
//       roleDefinitionId: roleAssignment.roleDefinitionId
//     }
//   }
// ]

output id string = foundryProject.id
output name string = foundryProject.name
output principalId string = foundryProject.identity.principalId
// Legacy connection string format - retained for backward compatibility
output connectionString string = '${location}.api.azureml.ms;${subscription().subscriptionId};${resourceGroup().name};${name}'
// New endpoint format required for Semantic Kernel 1.31.0+
output endpoint string = 'https://${name}.services.ai.azure.com/api/projects/${name}'
