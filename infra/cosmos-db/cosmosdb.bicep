@description('The location in which the resources should be deployed.')
param location string = resourceGroup().location

@description('The name of the Cosmos DB account.')
param accountName string

@description('The name of the database.')
param databaseName string

@description('Container specifications with different configurations')
param containerConfigurations array = [
  {
    name: 'chatHistory'
    partitionKey: '/partitionKey'
    enableVectorSearch: false
    enableFullTextSearch: false
  }
]

@description('The the partition key for the collections (backward compatibility).')
param partitionKey string = 'partitionKey'

@description('Embedding dimensions for vector search')
param embeddingDimensions int = 1536

param sqlRoleAssignments array = []

param tags object = {}

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2025-05-01-preview' = {
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

resource cosmosDbDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2025-05-01-preview' = {
  parent: cosmosDbAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource cosmosDbContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-05-01-preview' = [
  for config in containerConfigurations: {
    parent: cosmosDbDatabase
    name: config.name
    properties: {
      resource: union(
        {
          id: config.name
          partitionKey: {
            paths: [config.partitionKey]
            kind: 'Hash'
          }
          // TTL set to -1 means it is enabled for the container, but no automatic expiration of items
          defaultTtl: -1
        },
        config.enableVectorSearch
          ? {
              // Vector embedding policy for AI search
              vectorEmbeddingPolicy: {
                vectorEmbeddings: [
                  {
                    path: '/embedding'
                    dataType: 'float32'
                    distanceFunction: 'cosine'
                    dimensions: embeddingDimensions
                  }
                ]
              }
              // Indexing policy with vector indexes
              indexingPolicy: {
                indexingMode: 'consistent'
                automatic: true
                includedPaths: [
                  { path: '/*' }
                ]
                excludedPaths: [
                  { path: '/embedding/*' } // Exclude vector path for performance
                ]
                vectorIndexes: [
                  {
                    path: '/embedding'
                    type: 'diskANN'
                  }
                ]
                fullTextIndexes: config.enableFullTextSearch
                  ? [
                      {
                        path: '/content'
                      }
                    ]
                  : []
              }
            }
          : {
              // Basic indexing policy for non-vector containers
              indexingPolicy: {
                indexingMode: 'consistent'
                automatic: true
                includedPaths: [
                  { path: '/*' }
                ]
              }
            },
        config.enableFullTextSearch
          ? {
              // Full-text search policy for hybrid search
              fullTextPolicy: {
                defaultLanguage: 'en-US'
                fullTextPaths: [
                  {
                    path: '/content'
                    language: 'en-US'
                  }
                ]
              }
            }
          : {}
      )
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
output cosmosDbContainerNames array = [for config in containerConfigurations: config.name]
output cosmosDbEndpoint string = cosmosDbAccount.properties.documentEndpoint
output cosmosDbPartitionKey string = partitionKey
output cosmosDbId string = cosmosDbAccount.id
