param apimName string
param backendNames array
param backendPoolName string

resource apiManagementService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

resource backends 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = [
  for (name, i) in backendNames: {
    name: name
    parent: apiManagementService
    properties: {
      url: 'https://${name}.openai.azure.com/openai'
      protocol: 'http'
      description: 'Backend for ${name}'
      type: 'Single'
      circuitBreaker: {
        rules: [
          {
            acceptRetryAfter: true
            failureCondition: {
              count: 1
              interval: 'PT10S'
              statusCodeRanges: [
                {
                  min: 429
                  max: 429
                }
                {
                  min: 500
                  max: 503
                }
              ]
            }
            name: '${name}BreakerRule'
            tripDuration: 'PT10S'
          }
        ]
      }
    }
  }
]

resource aoailbpool 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  name: backendPoolName
  parent: apiManagementService
  properties: {
    description: 'Load balance multiple openai instances'
    type: 'Pool'
    pool: {
      services: [
        for (backend, i) in backendNames: {
          id: '/backends/${backendNames[i]}'
          priority: 1
          weight: 1
        }
      ]
    }
  }
  dependsOn: backends
}

output backendPoolName string = aoailbpool.name
