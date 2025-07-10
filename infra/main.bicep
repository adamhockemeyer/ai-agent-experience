@minLength(1)
@maxLength(64)
@description('Name of the the environment')
param environmentName string

@description('Azure region where resources should be deployed')
param location string

@description('Resource name prefix. If not provided, a valid default will be generated.')
param resourcePrefix string = '${substring(uniqueString(resourceGroup().id),0,4)}-aiagents'

// Ensure the prefix starts with a letter for resource naming compliance
var prefix = contains('abcdefghijklmnopqrstuvwxyz', toLower(substring(resourcePrefix, 0, 1)))
  ? resourcePrefix
  : 'a${resourcePrefix}'

@description('Array of OpenAI model deployments to create. If empty, default models will be used.')
param openAIDeployments array = []

@description('Version of the Azure OpenAI API to use. Used by the OpenAI API in API Management as well as the Azure Container Apps API.')
param azureOpenAIAPIVersion string = '2024-10-21'

param commonTags object = {
  created_by: 'bicep'
  project: 'AI Agent Experience'
  'azd-env-name': environmentName
  SecurityControl: 'Ignore'
}
param apimPublisherEmail string = 'user@company.com'
param apiAppExists bool = false
param webAppExists bool = false
param azureMapsLocation string

var sharedRoleDefinitions = loadJsonContent('./role-definitions.json')

module logAnalytics 'logs/log-analytics.bicep' = {
  name: '${prefix}-la'
  params: {
    location: location
    name: '${prefix}-la'
    commonTags: commonTags
  }
}

module applicationInsights 'logs/application-insights.bicep' = {
  name: '${prefix}-appinsights'
  params: {
    location: location
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
    containerNames: [
      'documents'
      'function-releases'
      'function-releases-api-sap'
    ]
  }
}

// Create multiple OpenAI Accounts to show Load Balancing in API Management

module cognitiveServices1 'cognitive-services/ai-account.bicep' = {
  name: '${prefix}-oai'
  params: {
    location: location
    name: '${prefix}-oai'
    commonTags: commonTags
    roleAssignments: [
      {
        principalId: apim.outputs.principalId
        roleDefinitionId: sharedRoleDefinitions['Cognitive Services OpenAI User']
      }
      {
        principalId: userAssignedManagedIdentity.properties.principalId
        roleDefinitionId: sharedRoleDefinitions['Cognitive Services OpenAI User']
      }
    ]
  }
}

module openAIDeployments1 'cognitive-services/openai-deployments.bicep' = {
  name: '${prefix}-oai-deployments-1'
  params: {
    cognitiveServicesAccountName: cognitiveServices1.outputs.name
    deployments: openAIDeployments
  }
}

var apimName = 'apim-${prefix}'
var apimSubscriptionName = 'aiagent-subscription'

module apim 'api-management/apim.bicep' = {
  name: '${prefix}-apim'
  params: {
    location: location
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
    apimLoggerName: apim.outputs.loggerName
    apiVersion: azureOpenAIAPIVersion
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



module cosmosDB 'cosmos-db/cosmosdb.bicep' = {
  name: '${prefix}-cosmosdb'
  params: {
    location: location
    accountName: '${prefix}-cosmosdb'
    databaseName: 'aiagents-db'
    collectionNames: [
      'chatHistory'
    ]
    partitionKey: 'partitionKey'
    tags: commonTags
    sqlRoleAssignments: [
      {
        principalId: userAssignedManagedIdentity.properties.principalId
        roleDefinitionId: sharedRoleDefinitions['Cosmos DB Built-in Data Contributor']
      }
      {
        principalId: az.deployer().objectId
        roleDefinitionId: sharedRoleDefinitions['Cosmos DB Built-in Data Contributor']
      }
    ]
  }
}

module appConfig 'app-configuration/app-configuration.bicep' = {
  name: '${prefix}-appconfig'
  params: {
    name: '${prefix}-appconfig'
    location: location
    tags: commonTags
    keyValues: [
      // Note: The website config is now handled by a separate module
    ]
    roleAssignments: [
      {
        principalId: userAssignedManagedIdentity.properties.principalId
        roleDefinitionId: sharedRoleDefinitions['App Configuration Data Owner']
      }
      {
        principalId: az.deployer().objectId
        principalType: 'User'
        roleDefinitionId: sharedRoleDefinitions['App Configuration Data Owner']
      }
    ]
  }
}

// Website config are properties stored in App Configuration
// The frontend web app will read these properties from App Configuration
module websiteConfig 'app-configuration/website-config.bicep' = {
  name: '${prefix}-website-config'
  params: {
    appConfigName: appConfig.outputs.name
    websiteName: 'AI Agent Experience'
    authenticationEnabled: false
    openAIDeployments: openAIDeployments1.outputs.deployments
    location: location
    identityId: userAssignedManagedIdentity.id // Pass the identity resource ID
  }
}

// Add a weather agent config to App Configuration
module weatherAgentConfig 'app-configuration/agent_weather_agent_config.bicep' = {
  name: '${prefix}-weather-agent-config'
  params: {
    appConfigName: appConfig.outputs.name
    apimName: apim.outputs.name
    apimSubscriptionName: apimSubscriptionName
    location: location
    identityId: userAssignedManagedIdentity.id // Pass the identity resource ID
  }
}

module playwrightAgentConfig 'app-configuration/agent_playwright_agent_config.bicep' = {
  name: '${prefix}-playwright-agent-config'
  params: {
    appConfigName: appConfig.outputs.name
    location: location
    identityId: userAssignedManagedIdentity.id // Pass the identity resource ID
  }
}

module sapAgentConfig 'app-configuration/agent_sap_agent_config.bicep' = {
  name: '${prefix}-sap-agent-config'
  params: {
    appConfigName: appConfig.outputs.name
    sapFunctionAppName: sapDemoAPIFunctionApp.outputs.name
    location: location
    identityId: userAssignedManagedIdentity.id // Pass the identity resource ID
  }
}

module orchestratorAgentConfig 'app-configuration/agent_orchestrator_agent_config.bicep' = {
  name: '${prefix}-orchestrator-agent-config'
  params: {
    appConfigName: appConfig.outputs.name
    location: location
    identityId: userAssignedManagedIdentity.id // Pass the identity resource ID
  }
}

module search 'ai-search/search.bicep' = {
  name: '${prefix}-search'
  params: {
    name: '${prefix}-search'
    location: location
    tags: commonTags
    sku: 'basic'
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    roleAssignments: [
      {
        principalId: userAssignedManagedIdentity.properties.principalId
        roleDefinitionId: sharedRoleDefinitions['Cognitive Services OpenAI User']
      }
    ]
  }
}

// Function App with Flex Consumption Plan
module functionAppPlan 'function-app/function-app-plan.bicep' = {
  name: '${prefix}-function-app-plan'
  params: {
    location: location
    name: '${prefix}-function-plan'
    tags: commonTags
    sku: {
      tier: 'FlexConsumption'
      name: 'FC1'
    }
  }
}

// Function App Site
module sapDemoAPIFunctionApp 'function-app/function-app-site.bicep' = {
  name: '${prefix}-function-app'
  params: {
    location: location
    name: '${prefix}-function-api-sap'
    appServicePlanId: functionAppPlan.outputs.resourceId
    tags: union(commonTags, { 'azd-service-name': 'api-sap' })
    identityType: 'UserAssigned'
    identityId: userAssignedManagedIdentity.id
    principalId: userAssignedManagedIdentity.properties.principalId
    applicationInsightsConnectionString: applicationInsights.outputs.connectionString
    storageAccountName: storageAccount.outputs.storageAccountName
    maximumInstanceCount: 40
    instanceMemoryMB: 512
    deploymentStorageContainerName: 'function-releases-api-sap'
    env: [
      {
        name: 'AZURE_CLIENT_ID'
        value: userAssignedManagedIdentity.properties.clientId
      }
    ]
  }
}

module keyVault 'keyvault/keyvault.bicep' = {
  name: '${prefix}-kv'
  params: {
    name: '${prefix}kv'
    location: location
    tags: commonTags
    roleAssignments: [
      {
        principalId: userAssignedManagedIdentity.properties.principalId
        roleDefinitionId: sharedRoleDefinitions['Key Vault Secrets Officer']
      }
      {
        principalId: appConfig.outputs.principalId
        roleDefinitionId: sharedRoleDefinitions['Key Vault Secrets Officer']
      }
    ]
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
  location: location
}

module containerRegistry 'container-apps/container-registry.bicep' = {
  name: '${prefix}-container-registry'
  params: {
    location: location
    name: '${replace(prefix, '-', '')}cr'
    tags: commonTags
  }
}

module apiContainerApp 'container-apps/container-app-upsert.bicep' = {
  name: '${prefix}-api-container-app'
  params: {
    name: 'api'
    location: location
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
        name: 'AZURE_CLIENT_ID'
        value: userAssignedManagedIdentity.properties.clientId
      }
      {
        name: 'AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING'
        value: applicationInsights.outputs.connectionString
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: apim.outputs.gatewayUrl
      }
      {
        // This is the API key for the OpenAI API in API Management
        name: 'AZURE_OPENAI_API_KEY'
        value: listSecrets(resourceId('Microsoft.ApiManagement/service/subscriptions', apimName, apimSubscriptionName), '2024-06-01-preview').primaryKey
      }
      {
        name: 'AZURE_OPENAI_API_VERSION'
        value: azureOpenAIAPIVersion
      }
      {
        name: 'AZURE_AI_ENDPOINT'
        value: 'https://${cognitiveServices1.outputs.name}.services.ai.azure.com/models'
      }
      {
        name: 'AZURE_AI_AGENT_ENDPOINT'
        value: aiProject.outputs.projectEndpoint
      }
      {
        name: 'AZURE_APP_CONFIG_ENDPOINT'
        value: appConfig.outputs.endpoint
      }
      {
        name: 'ACA_POOL_MANAGEMENT_ENDPOINT'
        value: sessionPools.outputs.Endpoint
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
        name: 'THREAD_STORAGE_TYPE'
        value: 'cosmosdb'
      }
      {
        name: 'COSMOS_DB_ENDPOINT'
        value: cosmosDB.outputs.cosmosDbEndpoint
      }
      {
        name: 'COSMOS_DB_DATABASE_NAME'
        value: cosmosDB.outputs.cosmosDbDatabaseName
      }
      {
        name: 'COSMOS_DB_CONTAINER_NAME'
        value: cosmosDB.outputs.cosmosDbContainerNames[0]
      }
      {
        name: 'COSMOS_DB_PARTITION_KEY'
        value: cosmosDB.outputs.cosmosDbPartitionKey
      }
    ]
    targetPort: 80
  }
}

module webContainerApp 'container-apps/container-app-upsert.bicep' = {
  name: '${prefix}-web-container-app'
  params: {
    name: 'web'
    location: location
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
        name: 'AZURE_CLIENT_ID'
        value: userAssignedManagedIdentity.properties.clientId
      }
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: applicationInsights.outputs.connectionString
      }
      {
        name: 'CHAT_API_ENDPOINT'
        value: apiContainerApp.outputs.uri
      }
      {
        name: 'AZURE_APPCONFIG_ENDPOINT'
        value: appConfig.outputs.endpoint
      }
    ]
    targetPort: 3000
  }
}

module sessionPools 'container-apps/container-app-session-pools.bicep' = {
  name: '${prefix}-session-pools'
  params: {
    location: location
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

module bing 'bing-grounding.bicep' = {
  name: '${prefix}-bing-grounding'
  params: {
    baseName: prefix
    tags: commonTags
  }
}

// module aiFoundryProject 'cognitive-services/ai-project.bicep' = {
//   name: '${prefix}-ai-foundry-project'
//   params: {
//     location: location
//     projectName: '${prefix}-ai-project'
//     projectDescription: 'AI Project for Agent Experience'
//     projectDisplayName: 'AI Agent Experience Project'

//     existingAiFoundryName: cognitiveServices1.outputs.name
//     existingCosmosDbAccountName: cosmosDB.outputs.cosmosDbAccountName
//     existingStorageAccountName: storageAccount.outputs.storageAccountName
//     existingAISearchAccountName: search.outputs.name
//     existingBingAccountName: bing.outputs.bingAccountName
//     existingWebApplicationInsightsResourceName: applicationInsights.outputs.name
//   }
// }

//AI Project
module aiProject 'cognitive-services/ai-project.bicep' = {
  name: '${prefix}-ai-project'
  params: {
    location: location
    accountName: cognitiveServices1.outputs.name
    projectName: '${prefix}-ai-project'
    projectDescription: 'AI Project for Agent Experience'
    displayName: 'AI Agent Experience Project'

    // Connect to existing resources
    aiSearchName: search.outputs.name
    aiSearchServiceResourceGroupName: resourceGroup().name
    aiSearchServiceSubscriptionId: subscription().subscriptionId

    cosmosDBName: cosmosDB.outputs.cosmosDbAccountName
    cosmosDBResourceGroupName: resourceGroup().name
    cosmosDBSubscriptionId: subscription().subscriptionId

    azureStorageName: storageAccount.outputs.storageAccountName
    azureStorageResourceGroupName: resourceGroup().name
    azureStorageSubscriptionId: subscription().subscriptionId

    // Connect to App Insights
    appInsightsName: applicationInsights.outputs.name
    appInsightsResourceGroupName: resourceGroup().name
    appInsightsSubscriptionId: subscription().subscriptionId

    // Connect to Bing Search
    bingSearchName: bing.outputs.bingAccountName
    bingSearchResourceGroupName: resourceGroup().name
    bingSearchSubscriptionId: subscription().subscriptionId
  }
}

module formatProjectWorkspaceId 'cognitive-services/format-project-workspace-id.bicep' = {
  name: '${prefix}-format-project-workspace-id'
  params: {
    projectWorkspaceId: aiProject.outputs.projectWorkspaceId
  }
}

module storageAccountRoleAssignment 'cognitive-services/azure-storage-account-role-assignment.bicep' = {
  name: '${prefix}-storage-account-role-assignment'
  scope: resourceGroup(subscription().subscriptionId, resourceGroup().name)
  params: {
    azureStorageName: storageAccount.outputs.storageAccountName
    projectPrincipalId: aiProject.outputs.projectPrincipalId
  }
}

module cosmosAccountRoleAssignments 'cognitive-services/cosmosdb-account-role-assignment.bicep' = {
  name: '${prefix}-cosmos-account-role-assignments'
  scope: resourceGroup(subscription().subscriptionId, resourceGroup().name)
  params: {
    cosmosDBName: cosmosDB.outputs.cosmosDbAccountName
    projectPrincipalId: aiProject.outputs.projectPrincipalId
  }
  dependsOn: [
    storageAccountRoleAssignment
  ]
}

module aiSearchRoleAssignments 'cognitive-services/ai-search-role-assignments.bicep' = {
  name: '${prefix}-ai-search-role-assignments'
  scope: resourceGroup(subscription().subscriptionId, resourceGroup().name)
  params: {
    aiSearchName: search.outputs.name
    projectPrincipalId: aiProject.outputs.projectPrincipalId
  }
  dependsOn:[
    cosmosAccountRoleAssignments, storageAccountRoleAssignment
  ]
}

module addProjectCapabilityHost 'cognitive-services/add-project-capability-host.bicep' = {
  name: '${prefix}-add-project-capability-host'
  params: {
    accountName: cognitiveServices1.outputs.name
    projectName: aiProject.outputs.projectName
    cosmosDBConnection: aiProject.outputs.cosmosDBConnection
    azureStorageConnection: aiProject.outputs.azureStorageConnection
    aiSearchConnection: aiProject.outputs.aiSearchConnection

    projectCapHost: 'projectagents'
    accountCapHost: 'accountagents'
  }
  dependsOn: [
    aiSearchRoleAssignments, cosmosAccountRoleAssignments, storageAccountRoleAssignment
  ]
}

module storageContainerRoleAssignment 'cognitive-services/blob-storage-container-role-assignments.bicep' = {
  name: '${prefix}-storage-container-role-assignment'
  params: {
    aiProjectPrincipalId: aiProject.outputs.projectPrincipalId
    storageName: storageAccount.outputs.storageAccountName
    workspaceId: formatProjectWorkspaceId.outputs.projectWorkspaceIdGuid
  }
  dependsOn: [
    addProjectCapabilityHost
  ]
}

module cosmosContainerRoleAssignment 'cognitive-services/cosmos-container-role-assignments.bicep' = {
  name: '${prefix}-cosmos-container-role-assignment'
  params: {
    projectPrincipalId: aiProject.outputs.projectPrincipalId
    cosmosAccountName: cosmosDB.outputs.cosmosDbAccountName
    projectWorkspaceId: formatProjectWorkspaceId.outputs.projectWorkspaceIdGuid
  }
  dependsOn: [
    addProjectCapabilityHost, storageContainerRoleAssignment
  ]
}


// Managed Identity to Agent Service Role Assignment
module aiUserRoleAssignmentUAMI 'auth/role-assignment.bicep' = {
  name: '${prefix}-ai-user-role-managed-identity'
  params: {
    principalId: userAssignedManagedIdentity.properties.principalId
    roleDefinitionId: sharedRoleDefinitions['Azure AI User']
  }
}

module vectorizationRoleAssignments './auth/ai-search-vectorization-assignments.bicep' = {
  name: 'ai-search-vectorization-role-assignments'
  params: {
    principals: [
      { principalId: az.deployer().objectId, principalType: 'User' }
    ]
  }
}

module logicAppStandard 'logic-apps/logic-app-standard.bicep' = {
  name: '${prefix}-logicapp-standard'
  params: {
    name: '${prefix}-logicapp'
    location: location
    tags: commonTags
    storageAccountName: storageAccount.outputs.storageAccountName
    storageAccountResourceGroup: resourceGroup().name
    appInsightsName: applicationInsights.outputs.name
    appInsightsResourceGroup: resourceGroup().name
    planName: '${prefix}-logicapp-plan'
    userAssignedIdentityResourceId: userAssignedManagedIdentity.id
  }
}

// App outputs
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output API_BASE_URL string = apiContainerApp.outputs.uri
output REACT_APP_WEB_BASE_URL string = webContainerApp.outputs.uri
output SERVICE_API_NAME string = apiContainerApp.outputs.name
output SERVICE_WEB_NAME string = webContainerApp.outputs.name


// AI Project outputs
output AI_PROJECT_NAME string = aiProject.outputs.projectName
output AI_PROJECT_ENDPOINT string = aiProject.outputs.projectEndpoint


output AZURE_STORAGE_ACCOUNT_NAME string = storageAccount.outputs.storageAccountName
output AZURE_SEARCH_SERVICE_NAME string = search.outputs.name
output AZURE_OPENAI_ENDPOINT string = cognitiveServices1.outputs.endpoint
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME string = openAIDeployments1.outputs.embeddingDeploymentName
