@minLength(1)
@maxLength(64)
@description('Name of the the environment')
param environmentName string
param prefix string = '${substring(uniqueString(resourceGroup().id),0,4)}-apichat'
param region string = resourceGroup().location
param commonTags object = {
  created_by: 'bicep'
  project: 'API Chat'
  'azd-env-name': environmentName
}
param apimPublisherEmail string = 'user@company.com'
param apiAppExists bool = false
param webAppExists bool = false
param azureMapsLocation string
param deploySQLServer bool = true

var sharedRoleDefinitions = loadJsonContent('./role-definitions.json')

module logAnalytics 'logs/log-analytics.bicep' = {
  name: '${prefix}-la'
  params: {
    location: region
    name: '${prefix}-la'
    commonTags: commonTags
  }
}

module applicationInsights 'logs/application-insights.bicep' = {
  name: '${prefix}-appinsights'
  params: {
    location: region
    name: '${prefix}-appinsights'
    commonTags: commonTags
    logAnalyticsWorkspaceResourceId: logAnalytics.outputs.resourceId
  }
}

module storageAccount 'storage/storage.bicep' = {
  name: '${prefix}sa'
  params: {
    name: replace(replace('${prefix}storage', '-', ''), '_', '')
    tags: commonTags
  }
}

// Create multiple OpenAI Accounts to show Load Balancing in API Management

module cognitiveServices1 'cognitive-services/cognitive-services-openai.bicep' = {
  name: '${prefix}-oai-1'
  params: {
    location: region
    name: '${prefix}-oai-1'
    commonTags: commonTags
    roleAssignments: [
      {
        principalId: apim.outputs.principalId
        roleDefinitionId: sharedRoleDefinitions['Cognitive Services OpenAI User']
      }
    ]
  }
}

module openAIDeployments1 'cognitive-services/openai-deployments.bicep' = {
  name: '${prefix}-oai-deployments-1'
  params: {
    cognitiveServicesAccountName: cognitiveServices1.outputs.name
  }
}

module cognitiveServices2 'cognitive-services/cognitive-services-openai.bicep' = {
  name: '${prefix}-oai-2'
  params: {
    location: 'Sweden Central'
    name: '${prefix}-oai-2'
    commonTags: commonTags
    roleAssignments: [
      {
        principalId: apim.outputs.principalId
        roleDefinitionId: sharedRoleDefinitions['Cognitive Services OpenAI User']
      }
    ]
  }
}

module openAIDeployments2 'cognitive-services/openai-deployments.bicep' = {
  name: '${prefix}-oai-deployments-2'
  params: {
    cognitiveServicesAccountName: cognitiveServices2.outputs.name
  }
}

var apimName = 'apim-${prefix}'
var apimSubscriptionName = 'apichat-subscription'

module apim 'api-management/apim.bicep' = {
  name: '${prefix}-apim'
  params: {
    location: region
    name: apimName
    commonTags: commonTags
    publisherEmail: apimPublisherEmail
    publisherName: 'apim-${prefix}'
    appInsightsName: applicationInsights.name
    subscriptionName: apimSubscriptionName
    roleAssignments: [
      {
        principalId: ''
        roleDefinitionId: sharedRoleDefinitions['API Management Service Reader Role']
      }
    ]
  }
}

module apimApisSwagger 'api-management/apis/swagger-api.bicep' = {
  name: '${prefix}-apim-swagger-api'
  params: {
    serviceName: apim.outputs.name
  }
}

module apimBackendsOpenAI 'api-management/apim-backends-aoai.bicep' = {
  name: '${prefix}-apim-openai-backends'
  params: {
    apimName: apim.outputs.name
    backendPoolName: 'openaibackendpool'
    backendNames: [
      cognitiveServices1.outputs.name
      cognitiveServices2.outputs.name
    ]
  }
}

module apimNameValueOpenAIPool 'api-management/apim-namevalue.bicep' = {
  name: '${prefix}-apim-namedvalue-openai-pool'
  params: {
    apiManagementServiceName: apim.outputs.name
    name: 'openai-backend-pool'
    displayName: 'OpenAI-Backend-Pool'
    value: apimBackendsOpenAI.outputs.backendPoolName
  }
}

module apimNamedValueOpenAINonLoadBalancedPool 'api-management/apim-namevalue.bicep' = {
  name: '${prefix}-apim-namedvalue-openai-non-load-balanced-pool'
  params: {
    name: 'non-load-balanced-openai-backend-name'
    apiManagementServiceName: apim.outputs.name
    displayName: 'non-load-balanced-openai-backend-name'
    value: cognitiveServices1.outputs.name
  }
}

module apimApisOpenAI 'api-management/apis/openai-api.bicep' = {
  name: '${prefix}-apim-openai-api'
  params: {
    serviceName: apim.outputs.name
    backendName: apimBackendsOpenAI.outputs.backendPoolName
    apimLoggerName: apim.outputs.loggerName
  }
  dependsOn: [
    apimNameValueOpenAIPool
    apimNamedValueOpenAINonLoadBalancedPool
  ]
}

module maps 'maps/maps.bicep' = {
  name: '${prefix}-maps'
  params: {
    location: azureMapsLocation
    name: '${prefix}-maps'
    tags: commonTags
    storageAccountName: storageAccount.name
    roleAssignments: [
      {
        principalId: apim.outputs.principalId
        roleDefinitionId: sharedRoleDefinitions['Azure Maps Data Reader']
      }
    ]
  }
}

module apimNamedValueMapsId 'api-management/apim-namevalue.bicep' = {
  name: '${prefix}-apim-namedvalue-maps-id'
  params: {
    apiManagementServiceName: apim.outputs.name
    name: 'maps-clientId'
    displayName: 'Azure-Maps-Client-ID'
    value: maps.outputs.clientId
  }
}

module apimApisMaps 'api-management/apis/maps-api.bicep' = {
  name: '${prefix}-apim-maps-api'
  params: {
    serviceName: apim.outputs.name
  }
  dependsOn: [
    apimNamedValueMapsId
  ]
}

// Generic Chat Agent Product
module apimProduct_generic_chat_agent 'api-management/apim-product.bicep' = {
  name: '${prefix}-apim-product-generic-chat-agent'
  params: {
    apiManagementServiceName: apim.outputs.name
    productName: 'generic-chat-agent'
    productDisplayName: 'Generic Chat Agent'
    productDescription: 'This product has all available APIs enabled for the Chat Agent'
    productTerms: 'API Chat Product Terms'
    productApis: [
      apimApisMaps.outputs.id
    ]
  }
}

// Generic Chat Agent Instructions
module apimNameValue_generic_chat_agent_instructions 'api-management/apim-namevalue.bicep' = {
  name: '${prefix}-apim-namedvalue-generic-chat-agent-instructions'
  params: {
    apiManagementServiceName: apim.outputs.name
    name: '${apimProduct_generic_chat_agent.outputs.productName}-instructions'
    displayName: '${apimProduct_generic_chat_agent.outputs.productName}-instructions'
    value: loadTextContent('api-management/named-values/generic-chat-agent-instructions.md')
  }
}

module apimNamedValueAdventureWorksAPI 'api-management/apim-namevalue.bicep' = {
  name: '${prefix}-apim-namedvalue-adventureworks-service-url'
  params: {
    apiManagementServiceName: apimService.name
    name: 'adventureworks-api-service-url'
    displayName: 'Adventureworks-API-Service-URL'
    value: '${adventureWorksDABAPIContainerApp.outputs.uri}/api'
  }
}

module apimApisAdventureWorks 'api-management/apis/adventureworks-api.bicep' = {
  name: '${prefix}-apim-aw-api'
  params: {
    serviceName: apim.outputs.name
  }
  dependsOn: [
    apimNamedValueAdventureWorksAPI
  ]
}

// Generic Chat Agent Product
module apimProduct_field_support_agent 'api-management/apim-product.bicep' = {
  name: '${prefix}-apim-product-field-support-agent'
  params: {
    apiManagementServiceName: apim.outputs.name
    productName: 'field-support-agent'
    productDisplayName: 'Field Support Agent'
    productDescription: 'This product has all available APIs enabled for the Field Support Agent'
    productTerms: 'API Chat Product Terms'
    productApis: [
      apimApisAdventureWorks.outputs.id
    ]
  }
}

// Generic Chat Agent Instructions
module apimNameValue_field_support_agent_instructions 'api-management/apim-namevalue.bicep' = {
  name: '${prefix}-apim-namedvalue-field-support-agent-instructions'
  params: {
    apiManagementServiceName: apim.outputs.name
    name: '${apimProduct_field_support_agent.outputs.productName}-instructions'
    displayName: '${apimProduct_field_support_agent.outputs.productName}-instructions'
    value: loadTextContent('api-management/named-values/field-support-agent-instructions.md')
  }
}

module cosmosDB 'cosmos-db/cosmosdb.bicep' = {
  name: '${prefix}-cosmosdb'
  params: {
    location: 'East US2'
    accountName: '${prefix}-cosmosdb'
    databaseName: 'apichat-db'
    collectionNames: [
      'chatHistory'
    ]
    tags: commonTags
  }
}

module containerAppsEnvironment 'container-apps/container-app-environment.bicep' = {
  name: '${prefix}-container-app-environment'
  params: {
    containerAppsName: prefix
    workspaceResourceName: logAnalytics.outputs.workspaceName
    tags: commonTags
  }
}

resource userAssignedManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-identity'
  location: region
}

module containerRegistry 'container-apps/container-registry.bicep' = {
  name: '${prefix}-container-registry'
  params: {
    location: region
    name: '${replace(prefix, '-', '')}cr'
    tags: commonTags
  }
}

resource apimService 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

resource apimSubscription 'Microsoft.ApiManagement/service/subscriptions@2023-09-01-preview' existing = {
  name: apimSubscriptionName
  parent: apimService
}

module apiContainerApp 'container-apps/container-app-upsert.bicep' = {
  name: '${prefix}-api-container-app'
  params: {
    name: 'api'
    location: region
    tags: union(commonTags, { 'azd-service-name': 'api' })
    identityType: 'UserAssigned'
    identityName: userAssignedManagedIdentity.name
    exists: apiAppExists
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.containerAppsEnvironmentName
    containerRegistryName: containerRegistry.outputs.name
    containerCpuCoreCount: '1.0'
    containerMemory: '2.0Gi'
    env: [
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: applicationInsights.outputs.connectionString
      }
      {
        name: 'AZURE_OPENAI_API_KEY'
        value: apimSubscription.listSecrets().primaryKey
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: apim.outputs.gatewayUrl
      }
      {
        name: 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME'
        value: openAIDeployments1.outputs.chatDeploymentName
      }
      {
        name: 'AZURE_OPENAI_API_VERSION'
        value: '2024-10-01-preview'
      }
      {
        name: 'AZURE_APIM_ENDPOINT'
        value: apim.outputs.gatewayUrl
      }
      {
        name: 'AZURE_APIM_SERVICE_API_VERSION'
        value: '2022-08-01'
      }
      {
        name: 'AZURE_APIM_SERVICE_SUBSCRIPTION_KEY'
        value: apimSubscription.listSecrets().primaryKey
      }
      {
        name: 'AZURE_APIM_APICHAT_SUBSCRIPTION_KEY'
        value: apimSubscription.listSecrets().primaryKey
      }
      {
        name: 'SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS'
        value: 'true'
      }
      {
        name: 'SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE'
        value: 'true'
      }
      {
        name: 'OTEL_SERVICE_NAME'
        value: 'apichat-api'
      }
    ]
    targetPort: 80
  }
}

module webContainerApp 'container-apps/container-app-upsert.bicep' = {
  name: '${prefix}-web-container-app'
  params: {
    name: 'web'
    location: region
    tags: union(commonTags, { 'azd-service-name': 'web' })
    identityType: 'UserAssigned'
    identityName: userAssignedManagedIdentity.name
    exists: webAppExists
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.containerAppsEnvironmentName
    containerRegistryName: containerRegistry.outputs.name
    containerCpuCoreCount: '1.0'
    containerMemory: '2.0Gi'
    env: [
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: applicationInsights.outputs.connectionString
      }
      {
        name: 'SK_API_ENDPOINT'
        value: apiContainerApp.outputs.uri
      }
      {
        name: 'GENERIC_CHAT_APIM_PRODUCT_ID'
        value: apimProduct_generic_chat_agent.outputs.productName
      }
    ]
    targetPort: 3000
  }
}

module sqlServer 'sql/sql-server.bicep' = if (deploySQLServer) {
  name: '${prefix}-sql-server'
  params: {
    name: '${prefix}-sql'
    //location: region
    location: 'eastus2'
    tags: commonTags
    managedIdentityName: userAssignedManagedIdentity.name
    managedIdnetityClientId: userAssignedManagedIdentity.properties.principalId
  }
}

module adventureWorksDABAPIContainerApp 'container-apps/container-app-upsert.bicep' = if (deploySQLServer) {
  name: '${prefix}-aw-api-app'
  params: {
    name: 'adventureworks-api'
    location: region
    tags: union(commonTags, { 'azd-service-name': 'adventureworks-api' })
    identityType: 'UserAssigned'
    identityName: userAssignedManagedIdentity.name
    exists: webAppExists
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.containerAppsEnvironmentName
    containerRegistryName: containerRegistry.outputs.name
    containerCpuCoreCount: '1.0'
    containerMemory: '2.0Gi'
    secrets: {
      'azure-sql-connection-string': 'Server=tcp:${sqlServer.outputs.fullyQualifiedDomainName},1433;Initial Catalog=AdventureWorksLT;Authentication=Active Directory Default;'
      'user-assigned-managed-identity-client-id': userAssignedManagedIdentity.properties.clientId
    }
    env: [
      {
        name: 'AZURE_SQL_CONNECTION_STRING'
        secretRef: 'azure-sql-connection-string'
      }
      {
        name: 'AZURE_CLIENT_ID'
        secretRef: 'user-assigned-managed-identity-client-id'
      }
    ]
    targetPort: 5000
  }
}

module adventureWorksDABWebContainerApp 'container-apps/container-app-upsert.bicep' = if (deploySQLServer) {
  name: '${prefix}-aw-web-app'
  params: {
    name: 'adventureworks-web'
    location: region
    tags: union(commonTags, { 'azd-service-name': 'adventureworks-web' })
    identityType: 'UserAssigned'
    identityName: userAssignedManagedIdentity.name
    exists: webAppExists
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.containerAppsEnvironmentName
    containerRegistryName: containerRegistry.outputs.name
    containerCpuCoreCount: '1.0'
    containerMemory: '2.0Gi'
    secrets: {
      'data-api-builder-endpoint': '${adventureWorksDABAPIContainerApp.outputs.uri}/graphql'
    }
    env: [
      {
        name: 'CONFIGURATION__DATAAPIBUILDER__BASEAPIURL'
        secretRef: 'data-api-builder-endpoint'
      }
    ]
    targetPort: 8080
  }
}

module sessionPools 'container-apps/container-app-session-pools.bicep' = {
  name: '${prefix}-session-pools'
  params: {
    location: region
    name: 'session-pools-${prefix}'
    tags: commonTags
    roleAssignments: [
      {
        principalId: userAssignedManagedIdentity.properties.principalId
        roleDefinitionId: sharedRoleDefinitions['Azure ContainerApps Session Executor']
      }
    ]
  }
}

// App outputs
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name
output AZURE_LOCATION string = region
output AZURE_TENANT_ID string = tenant().tenantId
output API_BASE_URL string = apiContainerApp.outputs.uri
output REACT_APP_WEB_BASE_URL string = webContainerApp.outputs.uri
output SERVICE_API_NAME string = apiContainerApp.outputs.name
output SERVICE_WEB_NAME string = webContainerApp.outputs.name
