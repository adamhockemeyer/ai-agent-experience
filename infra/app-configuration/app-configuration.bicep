param name string
param tags object = {}
param location string
param skuName string = 'Standard'
param roleAssignments array = []
@description('Key/value pairs to be added to the App Configuration')
param keyValues array = []

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2024-05-01' = {
  name: name
  location: location
  sku: {
    name: skuName
  }
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    enablePurgeProtection: false
    dataPlaneProxy: {
      authenticationMode: 'Pass-through'
    }
  }
}

resource roleAssignmentsResource 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleAssignment in roleAssignments: {
    name: guid(roleAssignment.principalId, roleAssignment.roleDefinitionId, appConfig.id)
    scope: appConfig
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleAssignment.roleDefinitionId)
      principalId: roleAssignment.principalId
      principalType: roleAssignment.?principalType ?? 'ServicePrincipal'
    }
  }
]

@description('Create key/value pairs in App Configuration')
resource configKeyValues 'Microsoft.AppConfiguration/configurationStores/keyValues@2024-05-01' = [
  for keyValue in keyValues: {
    parent: appConfig
    name: keyValue.key
    properties: {
      value: keyValue.value
      contentType: keyValue.?contentType ?? null
      tags: keyValue.?tags ?? null
    }
  }
]

output id string = appConfig.id
output name string = appConfig.name
output principalId string = appConfig.identity.principalId
output endpoint string = appConfig.properties.endpoint
