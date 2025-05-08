@description('The location in which the resources should be deployed.')
param location string = resourceGroup().location

@description('The name of the Cosmos DB account.')
param accountName string

@description('The name of the database.')
param databaseName string

@description('The names of the collections within the database.')
param collectionNames array

@description('The the partition key for the collections.')
param partitionKey string = 'partitionKey'

param sqlRoleAssignments array = []

param tags object = {}

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [{ name: 'EnableNoSQLVectorSearch' }]
    locations: [
      {
        locationName: location
      }
    ]
  }
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
}

resource cosmosDbDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-12-01-preview' = {
  parent: cosmosDbAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource cosmosDbContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-12-01-preview' = [
  for collection in collectionNames: {
    parent: cosmosDbDatabase
    name: collection
    properties: {
      resource: {
        id: collection
        partitionKey: {
          paths: ['/${partitionKey}']
          kind: 'Hash'
        }
      }
      options: {
        autoscaleSettings: {
          maxThroughput: 4000
        }
      }
    }
  }
]

resource roleAssignmentsResource 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = [
  for roleAssignment in sqlRoleAssignments: if (length(roleAssignment) > 0) {
    name: guid(roleAssignment.principalId, roleAssignment.roleDefinitionId, cosmosDbAccount.id)
    parent: cosmosDbAccount
    properties: {
      roleDefinitionId: '${subscription().id}/resourceGroups/${resourceGroup().name}/providers/Microsoft.DocumentDB/databaseAccounts/${cosmosDbAccount.name}/sqlRoleDefinitions/${roleAssignment.roleDefinitionId}'
      principalId: roleAssignment.principalId
      scope: cosmosDbAccount.id
    }
  }
]

output cosmosDbAccountName string = cosmosDbAccount.name
output cosmosDbDatabaseName string = cosmosDbDatabase.name
output cosmosDbContainerNames array = [for collection in collectionNames: collection]
output cosmosDbEndpoint string = cosmosDbAccount.properties.documentEndpoint
output cosmosDbPartitionKey string = partitionKey
output cosmosDbId string = cosmosDbAccount.id
