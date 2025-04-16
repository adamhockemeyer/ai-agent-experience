param location string = resourceGroup().location
param name string
param commonTags object = {}


resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  #disable-next-line BCP334
  name: name
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
  tags: commonTags
}

output resourceId string = logAnalytics.id
output workspaceName string = name
