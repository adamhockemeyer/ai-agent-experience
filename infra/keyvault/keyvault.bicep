param name string
param location string = resourceGroup().location
param tags object = {}
param skuName string = 'standard'
param skuFamily string = 'A'

@description('Optional array of role assignments')
param roleAssignments array = []

@description('Soft delete retention period in days')
param softDeleteRetentionInDays int = 90

@description('Enable RBAC for data access instead of access policies')
param enableRbacAuthorization bool = true

@description('Whether to enable purge protection')
param enablePurgeProtection bool = true

resource keyVault 'Microsoft.KeyVault/vaults@2024-12-01-preview' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      name: skuName
      family: skuFamily
    }
    enableRbacAuthorization: enableRbacAuthorization
    enableSoftDelete: true
    softDeleteRetentionInDays: softDeleteRetentionInDays
    enablePurgeProtection: enablePurgeProtection
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Create role assignments if provided
resource roleAssignmentsResource 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleAssignment in roleAssignments: if (length(roleAssignments) > 0) {
    name: guid(roleAssignment.principalId, roleAssignment.roleDefinitionId, keyVault.id)
    scope: keyVault
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleAssignment.roleDefinitionId)
      principalId: roleAssignment.principalId
      principalType: 'ServicePrincipal'
    }
  }
]

output id string = keyVault.id
output name string = keyVault.name
output uri string = keyVault.properties.vaultUri

