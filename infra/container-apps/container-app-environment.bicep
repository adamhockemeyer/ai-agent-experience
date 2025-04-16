param containerAppsName string
param workspaceResourceName string
param tags object = {}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceResourceName
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${containerAppsName}-ca-env'
  location: resourceGroup().location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        workloadProfileType: 'Consumption'
        name: 'Consumption'
      }
    ]
  }
}

output containerAppsEnvironmentResourceId string = containerAppsEnvironment.id
output consumptionWorkloadProfileName string = containerAppsEnvironment.properties.workloadProfiles[0].name
output containerAppsEnvironmentName string = containerAppsEnvironment.name
