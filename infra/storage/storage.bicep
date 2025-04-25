param name string
param tags object = {}
param containerNames array = []

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  sku: {
    name: 'Standard_RAGRS'
  }
  kind: 'StorageV2'
  name: name
  location: resourceGroup().location
  tags: tags
  properties: {
    dnsEndpointType: 'Standard'
    defaultToOAuthAuthentication: false
    publicNetworkAccess: 'Enabled'
    allowCrossTenantReplication: false
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    largeFileSharesState: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      virtualNetworkRules: []
      ipRules: []
      defaultAction: 'Allow'
    }
    supportsHttpsTrafficOnly: true
    encryption: {
      requireInfrastructureEncryption: false
      services: {
        file: {
          keyType: 'Account'
          enabled: true
        }
        blob: {
          keyType: 'Account'
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
    accessTier: 'Hot'
  }
  identity: {
    type: 'SystemAssigned'
  }
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for containerName in containerNames: {
  parent: blobServices
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}
]

output storageAccountName string = storage.name
output containerNames array = containerNames
output id string = storage.id
