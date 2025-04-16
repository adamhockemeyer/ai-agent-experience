param name string
param tags object = {}
param location string
param managedIdentityName string
param managedIdnetityClientId string

module server 'br/public:avm/res/sql/server:0.12.0' = {
  name: 'sql-server'
  params: {
    name: name
    location: location
    tags: tags
    publicNetworkAccess: 'Enabled'
    administrators: {
      azureADOnlyAuthentication: true
      login: managedIdentityName
      principalType: 'Application'
      sid: managedIdnetityClientId
      tenantId: tenant().tenantId
    }
    firewallRules: [
      {
        name: 'AllowAllAzureInternal'
        startIpAddress: '0.0.0.0'
        endIpAddress: '0.0.0.0'
      }
    ]
    databases: [
      {
        name: 'adventureworkslt'
        sku: {
          name: 'Standard'
          tier: 'Standard'
        }
        sampleName: 'AdventureWorksLT'
        maxSizeBytes: 268435456000
        zoneRedundant: false
      }
    ]
  }
}

output serverName string = server.outputs.name
output fullyQualifiedDomainName string = server.outputs.fullyQualifiedDomainName
