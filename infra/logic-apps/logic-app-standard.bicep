// filepath: infra/logic-apps/logic-app-standard.bicep
// Module to deploy an Azure Logic Apps Standard resource with required dependencies

@description('Name of the Logic App')
param name string

@description('Azure region for the Logic App')
param location string

@description('Tags to apply to the Logic App')
param tags object = {}

@description('Name of the Storage Account to use for Logic App state')
param storageAccountName string

@description('Resource group of the Storage Account (optional, defaults to current)')
param storageAccountResourceGroup string = resourceGroup().name

@description('Name of the Application Insights resource')
param appInsightsName string

@description('Resource group of the Application Insights (optional, defaults to current)')
param appInsightsResourceGroup string = resourceGroup().name

@description('Name of the App Service Plan (Elastic Premium, WS1)')
param planName string

@description('Resource ID of the User Assigned Managed Identity to assign to the Logic App')
param userAssignedIdentityResourceId string

// Get storage account connection string
var storageAccountId = resourceId(storageAccountResourceGroup, 'Microsoft.Storage/storageAccounts', storageAccountName)
var storageAccountKeys = listKeys(storageAccountId, '2022-09-01')
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccountKeys.keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

// Get Application Insights instrumentation key
var appInsightsId = resourceId(appInsightsResourceGroup, 'Microsoft.Insights/components', appInsightsName)
var appInsights = reference(appInsightsId, '2020-02-02')

// App Service Plan (Elastic Premium, WS1)
resource logicAppPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: planName
  location: location
  sku: {
    name: 'WS1'
    tier: 'ElasticPremium'
  }
  kind: 'elastic'
  tags: tags
}

// Logic App Standard (workflowapp)
resource logicApp 'Microsoft.Web/sites@2022-09-01' = {
  name: name
  location: location
  kind: 'functionapp,workflowapp'
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityResourceId}': {}
    }
  }
  properties: {
    serverFarmId: logicAppPlan.id
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: storageConnectionString
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(replace(name, '_', '-'))
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.ConnectionString
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'dotnet'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'APP_KIND'
          value: 'workflowapp'
        }
      ]
      alwaysOn: true
      ftpsState: 'Disabled'
    }
    httpsOnly: true
  }
}

output logicAppName string = logicApp.name
output logicAppResourceId string = logicApp.id
output logicAppDefaultHostName string = logicApp.properties.defaultHostName
