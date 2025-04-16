// Parameters
@description('Specifies the role definition ID used in the role assignment.')
param roleDefinitionId string

@description('Specifies the principal ID assigned to the role.')
param principalId string


var roleAssignmentName= guid(principalId, roleDefinitionId, resourceGroup().id)
// Create the role assignment
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentName
  properties: {
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output name string = roleAssignment.name
output resourceGroupName string = resourceGroup().name
output resourceId string = roleAssignment.id
