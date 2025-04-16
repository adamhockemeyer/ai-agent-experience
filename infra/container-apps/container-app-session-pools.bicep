@description('The location in which the resources should be deployed.')
param location string = resourceGroup().location

@description('The name of the resource.')
param name string

param tags object = {}

param roleAssignments array = []

resource caSessionPools 'Microsoft.App/sessionPools@2024-10-02-preview' = {
  name: name
  location: location
//   Managed Identity is only supported for custom containers
//   identity: {
//     type: normalizedIdentityType
//     userAssignedIdentities: !empty(identityName) && normalizedIdentityType == 'UserAssigned' ? { '${userIdentity.id}': {} } : null
//   }
  properties: {
    containerType: 'PythonLTS'
    poolManagementType: 'Dynamic'
    sessionNetworkConfiguration: {
      status: 'EgressEnabled'
    }
    dynamicPoolConfiguration: {
      cooldownPeriodInSeconds: 300
      executionType: 'Timed'
    }
    scaleConfiguration: {
      maxConcurrentSessions: 10
    }
  }
  tags: tags
}

resource roleAssignmentsResource 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleAssignment in roleAssignments: if(length(roleAssignment) > 0 ) {
    name: guid(roleAssignment.principalId, roleAssignment.roleDefinitionId, caSessionPools.id)
    scope: caSessionPools
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleAssignment.roleDefinitionId)
      principalId: roleAssignment.principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output Id string = caSessionPools.id
output Name string = caSessionPools.name
output Endpoint string = caSessionPools.properties.poolManagementEndpoint
