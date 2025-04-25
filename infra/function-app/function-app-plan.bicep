@description('Azure region where resources should be deployed')
param location string

@description('Name of the function app plan')
param name string

@description('Tags for all resources')
param tags object = {}

@description('Role assignments for the function app plan')
param roleAssignments array = []

@description('The SKU of the App Service Plan')
param sku object = {
  tier: 'FlexConsumption'
  name: 'FC1'
}

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: name
  location: location
  tags: tags
  kind: 'functionapp'
  sku: sku
  properties: {
    reserved: true // For Linux
  }
}

@description('Resource ID of the function app plan')
output resourceId string = appServicePlan.id

@description('Name of the function app plan')
output name string = appServicePlan.name
