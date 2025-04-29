// Assigns the necessary roles to the AI project

@description('Name of the AI Services resource')
param aiServicesName string

@description('Principal ID of the AI project')
param aiProjectPrincipalId string

@description('Resource ID of the AI project')
param aiProjectId string

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-06-01-preview' existing = {
  name: aiServicesName
  scope: resourceGroup()
}

var sharedRoleDefinitions = loadJsonContent('../role-definitions.json')

resource azureAIDeveloperRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: sharedRoleDefinitions['Azure AI Developer']
  scope: resourceGroup()
}

resource cognitiveServicesUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: aiServices
  name: guid(aiProjectId, azureAIDeveloperRole.id, aiServices.id)
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: azureAIDeveloperRole.id
    principalType: 'ServicePrincipal'
  }
}
