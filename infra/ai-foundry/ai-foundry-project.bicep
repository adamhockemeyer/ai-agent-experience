@description('The location into which the Azure AI resources should be deployed.')
param location string = resourceGroup().location

@description('Name of the AI Foundry Project resource')
param name string

@description('Tags to be applied to all deployed resources')
param tags object = {}

@description('The ID of the AI Foundry Hub to associate with this project.')
param hubId string

@description('Role assignments for the AI Foundry Project')
param roleAssignments array = []

@description('Optional deployment settings for models')
param modelDeployments array = []



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



@description('This module assigns the specified role to the AI Foundry Project resource')
module roleAssignment '../auth/role-assignment.bicep' = [
  for (roleAssignment, i) in roleAssignments: {
    name: '${name}-project-role-assignment-${i}'
    params: {
      principalId: roleAssignment.principalId
      roleDefinitionId: roleAssignment.roleDefinitionId
    }
  }
]

output id string = foundryProject.id
output name string = foundryProject.name
output principalId string = foundryProject.identity.principalId
