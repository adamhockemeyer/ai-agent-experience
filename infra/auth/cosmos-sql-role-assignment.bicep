@description('Specifies the principal ID assigned to the role.')
param principalId string

@description('Specifies the role definition ID used in the role assignment.')
param roleDefinitionId string

@description('The name of the Cosmos DB account')
param cosmosDbAccountName string

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' existing = {
  name: cosmosDbAccountName
}

// Create SQL role assignment for Cosmos DB
resource sqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  name: guid(principalId, roleDefinitionId, cosmosDbAccount.id)
  parent: cosmosDbAccount
  properties: {
    roleDefinitionId: '${subscription().id}/resourceGroups/${resourceGroup().name}/providers/Microsoft.DocumentDB/databaseAccounts/${cosmosDbAccountName}/sqlRoleDefinitions/${roleDefinitionId}'
    principalId: principalId
    scope: cosmosDbAccount.id
  }
}

output name string = sqlRoleAssignment.name
output id string = sqlRoleAssignment.id
