param cognitiveServicesAccountName string
@allowed([
  'GlobalBatch'
  'GlobalStandard'
  'GlobalProvisionedManaged'
  'Standard'
  'ProvisionedManaged'
])
param deploymentType string = 'GlobalStandard'
// Models to deploy
param deployments array = [
  {
    name: 'gpt-4o'
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-05-13'
    }
    sku: {
      name: deploymentType
      capacity: 150
    }
  }
  // text embendded only works with standard deployment sku at the moment
  {
    name: 'text-embedding-large'
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    sku: {
      name: 'Standard'
      capacity: 20
    }
  }
  // {
  //   name: 'dall-e-3'
  //   model: {
  //     format: 'OpenAI'
  //     name: 'dall-e-3'
  //     version: '3.0'
  //   }
  //   sku: {
  //     name: 'Standard'
  //     capacity: 2
  //   }
  // }
]

resource cognitiveServicesAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: cognitiveServicesAccountName
}

@batchSize(1)
resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [
  for deployment in deployments: {
    parent: cognitiveServicesAccount
    name: deployment.name
    sku: {
      name: deployment.sku.name
      capacity: deployment.sku.capacity
    }
    properties: {
      model: deployment.model
      raiPolicyName: 'Microsoft.Default'
      versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    }
  }
]

output chatDeploymentName string = deployment[0].name
output embeddingDeploymentName string = deployment[1].name
