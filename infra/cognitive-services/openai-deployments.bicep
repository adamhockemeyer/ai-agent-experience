param cognitiveServicesAccountName string
@allowed([
  'GlobalBatch'
  'GlobalStandard'
  'GlobalProvisionedManaged'
  'Standard'
  'ProvisionedManaged'
])
param deploymentType string = 'GlobalStandard'

@description('Array of OpenAI model deployments to create. This allows for flexible configurations based on region availability.')
param deployments array = []

// Default deployments if none are provided
var defaultDeployments = [
  {
    name: 'gpt-4o'
    model: {
      name: 'gpt-4o'
      version: '2024-11-20'
    }
    sku: {
      name: deploymentType
      capacity: 400
    }
  }
  // text embendded only works with standard deployment sku at the moment
  {
    name: 'text-embedding-large'
    model: {
      name: 'text-embedding-3-large'
      version: '1'
    }
    sku: {
      name: 'Standard'
      capacity: 20
    }
  }
]

// Use provided deployments or fall back to defaults
var deploymentsToCreate = !empty(deployments) ? deployments : defaultDeployments

resource cognitiveServicesAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: cognitiveServicesAccountName
}

@batchSize(1)
resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [
  for deployment in deploymentsToCreate: {
    parent: cognitiveServicesAccount
    name: deployment.name
    sku: {
      name: deployment.sku.name
      capacity: deployment.sku.capacity
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: deployment.model.name
        version: deployment.model.version
      }
      raiPolicyName: 'Microsoft.DefaultV2'
      versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    }
  }
]

@description('Name of the first deployment which can be used as default chat model')
output chatDeploymentName string = length(deploymentsToCreate) > 0 ? deployment[0].name : ''

@description('Name of the embedding model deployment, if available')
output embeddingDeploymentName string = length(deploymentsToCreate) > 1
  ? deployment[length(deploymentsToCreate) > 3 ? 3 : 1].name
  : ''

@description('Array of all deployed models with their details')
output deployments array = [
  for (deployment, i) in deploymentsToCreate: {
    name: deployment.name
    model: deployment.model.name
    sku: deployment.sku.name
    capacity: deployment.sku.capacity
    version: deployment.model.version
  }
]
