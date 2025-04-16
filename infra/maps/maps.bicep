
param name string
param tags object = {}
param location string
param storageAccountName string
param roleAssignments array = []


resource storage 'Microsoft.Storage/storageAccounts@2023-05-01'existing = {
  name: storageAccountName
}

resource maps 'Microsoft.Maps/accounts@2024-01-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'Gen2'
  sku: {
    name: 'G2'
  }
  properties: {
    disableLocalAuth: false
    linkedResources: [
      {
        id: storage.id
        uniqueName: 'default-storage-account'
      }
    ]
    cors: {
      corsRules: [
        {
          allowedOrigins: [
            '*'
          ]
        }
      ]
    }
    publicNetworkAccess: 'enabled'
    locations: []
  }
  
  identity: {
    type: 'SystemAssigned'
  }
}

resource roleAssignmentsResource 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleAssignment in roleAssignments: if(length(roleAssignment) > 0 ) {
    name: guid(roleAssignment.principalId, roleAssignment.roleDefinitionId, maps.id)
    scope: maps
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleAssignment.roleDefinitionId)
      principalId: roleAssignment.principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output clientId string = maps.properties.uniqueId
