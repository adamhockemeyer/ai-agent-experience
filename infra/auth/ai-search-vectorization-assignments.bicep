// Parameters
@description('Specifies the principals assigned to the roles (array of objects with principalId and principalType).')
param principals array = [
  {
    principalId: ''
    principalType: 'ServicePrincipal'
  }
]

@description('Scope for the role assignments - defaults to resource group')
param scope string = resourceGroup().id

// Role definitions
// From role-definitions.json
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// Built-in Azure roles not in role-definitions.json
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageAccountContributorRoleId = '17d1049b-9a84-46fb-8f53-869881c3d3ab'
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

// Azure Storage Roles
resource storageBlobDataContributorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principal in principals: {
    name: guid(principal.principalId, storageBlobDataContributorRoleId, scope)
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
      principalId: principal.principalId
      principalType: principal.principalType
    }
  }
]

resource storageAccountContributorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principal in principals: {
    name: guid(principal.principalId, storageAccountContributorRoleId, scope)
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', storageAccountContributorRoleId)
      principalId: principal.principalId
      principalType: principal.principalType
    }
  }
]

// resource readerRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principal in principals: {
//   name: guid(principal.principalId, readerRoleId, scope)
//   properties: {
//     roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', readerRoleId)
//     principalId: principal.principalId
//     principalType: principal.principalType
//   }
// }]

// Azure AI Search Roles
resource searchServiceContributorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principal in principals: {
    name: guid(principal.principalId, searchServiceContributorRoleId, scope)
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
      principalId: principal.principalId
      principalType: principal.principalType
    }
  }
]

resource searchIndexDataContributorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principal in principals: {
    name: guid(principal.principalId, searchIndexDataContributorRoleId, scope)
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
      principalId: principal.principalId
      principalType: principal.principalType
    }
  }
]

// Azure OpenAI Roles
resource cognitiveServicesOpenAIUserRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principal in principals: {
    name: guid(principal.principalId, cognitiveServicesOpenAIUserRoleId, scope)
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
      principalId: principal.principalId
      principalType: principal.principalType
    }
  }
]

resource cognitiveServicesUserRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principal in principals: {
    name: guid(principal.principalId, cognitiveServicesUserRoleId, scope)
    properties: {
      roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
      principalId: principal.principalId
      principalType: principal.principalType
    }
  }
]

// Outputs
output storageRoleAssignmentIds array = [
  for (principal, i) in principals: {
    blobDataContributor: storageBlobDataContributorRoleAssignments[i].id
    storageAccountContributor: storageAccountContributorRoleAssignments[i].id
  }
]

output searchRoleAssignmentIds array = [
  for (principal, i) in principals: {
    serviceContributor: searchServiceContributorRoleAssignments[i].id
    indexDataContributor: searchIndexDataContributorRoleAssignments[i].id
  }
]

output openAIRoleAssignmentIds array = [
  for (principal, i) in principals: {
    openAIUser: cognitiveServicesOpenAIUserRoleAssignments[i].id
    cognitiveServicesUser: cognitiveServicesUserRoleAssignments[i].id
  }
]
