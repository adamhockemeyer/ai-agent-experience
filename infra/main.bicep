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

@secure()
@description('Microsoft Agents SDK Client Secret for Bot Framework authentication')
param microsoftAgentsClientSecret string = ''
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
      'function-releases-api-mcp-search-index'
      'eventgrid-deadletter'
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
    containerConfigurations: [
      {
        name: 'chatHistory'
        partitionKey: '/partitionKey'
        enableVectorSearch: false
        enableFullTextSearch: false
      }
    ]
    partitionKey: 'partitionKey'
    embeddingDimensions: 1536 // Standard OpenAI embedding dimensions
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

// Separate database for document search index with vector and full-text search
module cosmosDocumentIndex 'cosmos-db/cosmosdb.bicep' = {
  name: '${prefix}-cosmos-document-index'
  params: {
    location: location
    accountName: '${prefix}-cosmosdb' // Use same account
    databaseName: 'DocumentIndex' // Separate database for search index
    containerConfigurations: [
      {
        name: 'chunks'
        partitionKey: '/document_id' // Partition by document ID for efficient queries
        enableVectorSearch: true
        enableFullTextSearch: true
      }
    ]
    partitionKey: 'document_id'
    embeddingDimensions: 1536
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
  dependsOn: [
    cosmosDB // Ensure main DB is created first
  ]
}

// Azure RBAC role assignments for Cosmos DB account management
resource cosmosDbContributorRoleAssignmentUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(az.deployer().objectId, sharedRoleDefinitions['DocumentDB Account Contributor'], '${prefix}-cosmosdb')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      sharedRoleDefinitions['DocumentDB Account Contributor']
    )
    principalId: az.deployer().objectId
    principalType: 'User'
  }
}

resource cosmosDbContributorRoleAssignmentMsi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(
    userAssignedManagedIdentity.name,
    sharedRoleDefinitions['DocumentDB Account Contributor'],
    '${prefix}-cosmosdb'
  )
  scope: resourceGroup()
  properties: {
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      sharedRoleDefinitions['DocumentDB Account Contributor']
    )
    principalId: userAssignedManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
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
    storageAccountName: storageAccount.outputs.storageAccountName
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
    storageAccountName: storageAccount.outputs.storageAccountName
  }
}

module sapAgentConfig 'app-configuration/agent_sap_agent_config.bicep' = {
  name: '${prefix}-sap-agent-config'
  params: {
    appConfigName: appConfig.outputs.name
    sapFunctionAppName: sapDemoAPIFunctionApp.outputs.name
    location: location
    identityId: userAssignedManagedIdentity.id // Pass the identity resource ID
    storageAccountName: storageAccount.outputs.storageAccountName
  }
}

module orchestratorAgentConfig 'app-configuration/agent_orchestrator_agent_config.bicep' = {
  name: '${prefix}-orchestrator-agent-config'
  params: {
    appConfigName: appConfig.outputs.name
    location: location
    identityId: userAssignedManagedIdentity.id // Pass the identity resource ID
    storageAccountName: storageAccount.outputs.storageAccountName
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

// Function App Infrastructure
// Azure Functions Flex Consumption plans can only host one function app each
// We create separate plans for each function app to ensure proper isolation

// Function App with Flex Consumption Plan for SAP Demo API
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

// Function App with Flex Consumption Plan for MCP Search Index
module mcpSearchIndexFunctionAppPlan 'function-app/function-app-plan.bicep' = {
  name: '${prefix}-mcp-search-index-function-app-plan'
  params: {
    location: location
    name: '${prefix}-mcp-search-index-function-plan'
    tags: commonTags
    sku: {
      tier: 'FlexConsumption'
      name: 'FC1'
    }
  }
}

// Function App Site for SAP Demo API
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

// MCP Search Index Function App
module mcpSearchIndexFunctionApp 'function-app/function-app-site.bicep' = {
  name: '${prefix}-function-app-mcp-search'
  params: {
    location: location
    name: '${prefix}-function-api-mcp-search-index'
    appServicePlanId: mcpSearchIndexFunctionAppPlan.outputs.resourceId
    tags: union(commonTags, { 'azd-service-name': 'api-mcp-search-index' })
    identityType: 'UserAssigned'
    identityId: userAssignedManagedIdentity.id
    principalId: userAssignedManagedIdentity.properties.principalId
    applicationInsightsConnectionString: applicationInsights.outputs.connectionString
    storageAccountName: storageAccount.outputs.storageAccountName
    maximumInstanceCount: 40
    instanceMemoryMB: 2048
    deploymentStorageContainerName: 'function-releases-api-mcp-search-index'
    env: [
      {
        name: 'AZURE_CLIENT_ID'
        value: userAssignedManagedIdentity.properties.clientId
      }
      {
        name: 'DOCUMENTS_STORAGE_CONNECTION_STRING'
        value: ''
      }
      {
        name: 'DOCUMENTS_STORAGE_ACCOUNT_URL'
        value: storageAccount.outputs.primaryBlobEndpoint
      }
      {
        name: 'DOCUMENTS_CONTAINER_NAME'
        value: 'documents'
      }
      {
        name: 'DocumentsStorage__blobServiceUri'
        value: storageAccount.outputs.primaryBlobEndpoint
      }
      {
        name: 'DocumentsStorage__queueServiceUri'
        value: storageAccount.outputs.primaryQueueEndpoint
      }
      {
        name: 'COSMOS_ENDPOINT'
        value: cosmosDocumentIndex.outputs.cosmosDbEndpoint
      }
      {
        name: 'COSMOS_DATABASE_NAME'
        value: cosmosDocumentIndex.outputs.cosmosDbDatabaseName
      }
      {
        name: 'COSMOS_CONTAINER_NAME'
        value: cosmosDocumentIndex.outputs.cosmosDbContainerNames[0]
      }
      {
        name: 'AZURE_SUBSCRIPTION_ID'
        value: subscription().subscriptionId
      }
      {
        name: 'AZURE_RESOURCE_GROUP'
        value: resourceGroup().name
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: apim.outputs.gatewayUrl
      }
      {
        name: 'AZURE_OPENAI_KEY'
        value: listSecrets(
          resourceId('Microsoft.ApiManagement/service/subscriptions', apimName, apimSubscriptionName),
          '2024-06-01-preview'
        ).primaryKey
      }
      {
        name: 'AZURE_OPENAI_EMBEDDING_MODEL'
        value: openAIDeployments1.outputs.embeddingDeploymentName
      }
      {
        name: 'AZURE_OPENAI_API_VERSION'
        value: azureOpenAIAPIVersion
      }
      {
        name: 'CHUNK_SIZE'
        value: '1000'
      }
      {
        name: 'CHUNK_OVERLAP'
        value: '200'
      }
      {
        name: 'MAX_TOKENS_PER_CHUNK'
        value: '8000'
      }
      {
        name: 'EMBEDDING_BATCH_SIZE'
        value: '16'
      }
      {
        name: 'EMBEDDING_DIMENSIONS'
        value: '1536'
      }
      {
        name: 'MAX_FILE_SIZE_MB'
        value: '100'
      }
      {
        name: 'SUPPORTED_EXTENSIONS'
        value: '.pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.html,.xlsx,.xls,.csv,.rtf,.odt,.png,.jpg,.jpeg,.bmp,.tiff,.gif'
      }
      {
        name: 'MAX_RETRIES'
        value: '3'
      }
      {
        name: 'RETRY_DELAY_SECONDS'
        value: '1'
      }
      {
        name: 'LOG_LEVEL'
        value: 'INFO'
      }
    ]
  }
}

// Ensure the deployment script identity can list Function App host keys
// Use deterministic name so scope can be calculated at the start of deployment
resource mcpFunctionAppExisting 'Microsoft.Web/sites@2023-01-01' existing = {
  name: '${prefix}-function-api-mcp-search-index'
}

// Assign Contributor role at the Function App scope to the User-Assigned Managed Identity
resource mcpFunctionAppContributorRoleAssignmentUAMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userAssignedManagedIdentity.id, mcpFunctionAppExisting.id, 'contributor')
  scope: mcpFunctionAppExisting
  properties: {
    // Website Contributor - sufficient for Microsoft.Web/sites/* including host/listkeys
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'de139f84-1756-47ae-9be6-808fbbe84772'
    )
    principalId: userAssignedManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
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

// Assign Storage Blob Data Contributor role to the user-assigned managed identity
// This ensures function apps using this identity can access storage without additional role assignments
resource storageAccountRoleAssignmentUAMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(
    userAssignedManagedIdentity.id,
    sharedRoleDefinitions['Storage Blob Data Contributor'],
    storageAccount.name
  )
  properties: {
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      sharedRoleDefinitions['Storage Blob Data Contributor']
    )
    principalId: userAssignedManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Assign Storage Queue Data Contributor role to the user-assigned managed identity
// This is required for the MCP function app's blob trigger to work with Event Grid
resource storageQueueRoleAssignmentUAMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(
    userAssignedManagedIdentity.id,
    sharedRoleDefinitions['Storage Queue Data Contributor'],
    storageAccount.name
  )
  properties: {
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      sharedRoleDefinitions['Storage Queue Data Contributor']
    )
    principalId: userAssignedManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Assign Storage Account Contributor role to allow management operations on the storage account
// (e.g., setting properties, listing keys if needed by downstream processes)
resource storageAccountContributorRoleAssignmentUAMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userAssignedManagedIdentity.id, sharedRoleDefinitions['Storage Account Contributor'], storageAccount.name)
  properties: {
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      sharedRoleDefinitions['Storage Account Contributor']
    )
    principalId: userAssignedManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// // Assign EventGrid Contributor role to the user-assigned managed identity
// // This allows the identity to create and manage Event Grid system topics and subscriptions
resource eventGridRoleAssignmentUAMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userAssignedManagedIdentity.id, sharedRoleDefinitions['EventGrid Contributor'], resourceGroup().id)
  properties: {
    roleDefinitionId: resourceId(
      'Microsoft.Authorization/roleDefinitions',
      sharedRoleDefinitions['EventGrid Contributor']
    )
    principalId: userAssignedManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- Event Grid System Topic auto-discovery / creation and subscription (replaces postdeploy script) ---
@description('Base name used if a new Event Grid system topic must be created')
var eventGridSystemTopicBaseName = '${prefix}-storage-topic'

// Deterministic Event Grid system topic for the storage account (idempotent create)
resource storageSystemTopic 'Microsoft.EventGrid/systemTopics@2023-12-15-preview' = {
  name: eventGridSystemTopicBaseName
  location: location
  properties: {
    source: resourceId('Microsoft.Storage/storageAccounts', storageAccount.outputs.storageAccountName)
    topicType: 'microsoft.storage.storageaccounts'
  }
  dependsOn: [
    storageAccount
  ]
}

// Event subscription targeting the MCP function's blob trigger function
resource storageBlobEventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2023-12-15-preview' = {
  parent: storageSystemTopic
  name: 'mcp-search-index-subscription'
  properties: {
    destination: {
      endpointType: 'AzureFunction'
      properties: {
        resourceId: '${mcpFunctionAppExisting.id}/functions/event_grid_blob_trigger'
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
        'Microsoft.Storage.BlobDeleted'
      ]
      subjectBeginsWith: '/blobServices/default/containers/documents/'
      subjectEndsWith: ''
      isSubjectCaseSensitive: false
    }
    deadLetterDestination: {
      endpointType: 'StorageBlob'
      properties: {
        resourceId: resourceId('Microsoft.Storage/storageAccounts', storageAccount.outputs.storageAccountName)
        blobContainerName: 'eventgrid-deadletter'
      }
    }
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
    eventDeliverySchema: 'EventGridSchema'
  }
  dependsOn: [
    mcpSearchIndexFunctionApp
  ]
}

module containerRegistry 'container-apps/container-registry.bicep' = {
  name: '${prefix}-container-registry'
  params: {
    location: location
    name: '${replace(prefix, '-', '')}cr'
    tags: commonTags
  }
}

// Bot Framework Service (created before API container app to avoid circular dependency)
module botService 'bot-service/bot-registration.bicep' = {
  name: '${prefix}-bot-service'
  params: {
    botName: '${prefix}-bot'
    botDisplayName: 'AI Agent Experience Bot'
    botDescription: 'AI Agent Bot for Microsoft Teams and Copilot integration'
    messagingEndpoint: 'https://placeholder-will-be-updated-after-deployment/api/messages'
    commonTags: commonTags
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
        value: listSecrets(
          resourceId('Microsoft.ApiManagement/service/subscriptions', apimName, apimSubscriptionName),
          '2024-06-01-preview'
        ).primaryKey
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
      // Environment variables for MCP Search Index
      {
        name: 'COSMOS_ENDPOINT'
        value: cosmosDocumentIndex.outputs.cosmosDbEndpoint
      }
      {
        name: 'COSMOS_DATABASE_NAME'
        value: cosmosDocumentIndex.outputs.cosmosDbDatabaseName
      }
      {
        name: 'COSMOS_CONTAINER_NAME'
        value: cosmosDocumentIndex.outputs.cosmosDbContainerNames[0]
      }
      {
        name: 'EMBEDDING_DIMENSIONS'
        value: '1536'
      }
      // Microsoft Agents SDK configuration
      {
        name: 'MICROSOFT_AGENTS_CLIENT_ID'
        value: botService.outputs.microsoftAppId
      }
      {
        name: 'MICROSOFT_AGENTS_CLIENT_SECRET'
        value: microsoftAgentsClientSecret
      }
      {
        name: 'MICROSOFT_AGENTS_TENANT_ID'
        value: botService.outputs.microsoftAppTenantId
      }
      {
        name: 'MICROSOFT_AGENTS_BOT_APP_ID'
        value: botService.outputs.microsoftAppId
      }
    ]
    targetPort: 8000
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

// Note: Microsoft Graph Bicep templates don't support creating client secrets
// The client secret must be created manually after deployment and stored in Key Vault
// You can use the following Azure CLI command after deployment:
// az ad app credential reset --id <APP_ID> --display-name "Bot Framework Secret" --years 2

// Update Bot Service messaging endpoint with actual API URL
resource updateBotMessagingEndpoint 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'updateBotMessagingEndpoint'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedManagedIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.50.0'
    storageAccountSettings: {
      storageAccountName: storageAccount.outputs.storageAccountName
      storageAccountKey: listKeys(storageAccountResourceId, '2023-05-01').keys[0].value
    }
    scriptContent: '''
      echo "Updating Bot Service messaging endpoint..."
      echo "Bot Name: ${BOT_NAME}"
      echo "Resource Group: ${RESOURCE_GROUP}"
      echo "API URL: ${API_URL}"
      
      # Update the Bot Service messaging endpoint
      az bot update \
        --name "${BOT_NAME}" \
        --resource-group "${RESOURCE_GROUP}" \
        --endpoint "${API_URL}/api/messages"
      
      echo "Bot Service messaging endpoint updated successfully"
    '''
    environmentVariables: [
      { name: 'BOT_NAME', value: botService.outputs.botServiceName }
      { name: 'RESOURCE_GROUP', value: resourceGroup().name }
      { name: 'API_URL', value: apiContainerApp.outputs.uri }
    ]
    timeout: 'PT5M'
    retentionInterval: 'PT1H'
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
  dependsOn: [
    cosmosAccountRoleAssignments
    storageAccountRoleAssignment
  ]
}

// Reference the storage account for deployment script settings
var storageAccountResourceId = resourceId(
  'Microsoft.Storage/storageAccounts',
  replace(replace('${prefix}storage', '-', ''), '_', '')
)

resource checkCapabilityHosts 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'checkCapabilityHosts'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedManagedIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.50.0'
    storageAccountSettings: {
      storageAccountName: storageAccount.outputs.storageAccountName
      storageAccountKey: listKeys(storageAccountResourceId, '2023-05-01').keys[0].value
    }
    scriptContent: '''
      # Debug: Print environment variables
      echo "Checking capability hosts..."
      echo "SUBSCRIPTION_ID: ${SUBSCRIPTION_ID}"
      echo "RESOURCE_GROUP: ${RESOURCE_GROUP}"
      echo "ACCOUNT_NAME: ${ACCOUNT_NAME}"
      echo "PROJECT_NAME: ${PROJECT_NAME}"
      echo "ACCOUNT_CAP_HOST: ${ACCOUNT_CAP_HOST}"
      echo "PROJECT_CAP_HOST: ${PROJECT_CAP_HOST}"
      
      # Check account capability host
      accountExists="false"
      account_url="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/capabilityHosts/${ACCOUNT_CAP_HOST}?api-version=2025-06-01"
      echo "Checking account capability host URL: ${account_url}"
      
      if az rest --method GET --url "${account_url}"; then
        echo "Account capability host EXISTS"
        accountExists="true"
      else
        echo "Account capability host does NOT exist"
        accountExists="false"
      fi
      
      # Check project capability host
      projectExists="false"
      project_url="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/projects/${PROJECT_NAME}/capabilityHosts/${PROJECT_CAP_HOST}?api-version=2025-06-01"
      echo "Checking project capability host URL: ${project_url}"
      
      if az rest --method GET --url "${project_url}"; then
        echo "Project capability host EXISTS"
        projectExists="true"
      else
        echo "Project capability host does NOT exist"
        projectExists="false"
      fi
      
      # Output results
      echo "Final results: accountExists=${accountExists}, projectExists=${projectExists}"
      echo "{\"accountCapHostExists\": ${accountExists}, \"projectCapHostExists\": ${projectExists}}" > $AZ_SCRIPTS_OUTPUT_PATH
    '''
    environmentVariables: [
      { name: 'SUBSCRIPTION_ID', value: subscription().subscriptionId }
      { name: 'RESOURCE_GROUP', value: resourceGroup().name }
      { name: 'ACCOUNT_NAME', value: cognitiveServices1.outputs.name }
      { name: 'PROJECT_NAME', value: aiProject.outputs.projectName }
      { name: 'ACCOUNT_CAP_HOST', value: 'accountagents' }
      { name: 'PROJECT_CAP_HOST', value: 'projectagents' }
    ]
    timeout: 'PT5M'
    retentionInterval: 'PT1H'
  }
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

    accountCapHostExists: bool(checkCapabilityHosts.properties.outputs.accountCapHostExists)
    projectCapHostExists: bool(checkCapabilityHosts.properties.outputs.projectCapHostExists)
  }
  dependsOn: [
    aiSearchRoleAssignments
    cosmosAccountRoleAssignments
    storageAccountRoleAssignment
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
    addProjectCapabilityHost
    storageContainerRoleAssignment
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
output AZURE_FUNCTIONAPP_MCP_NAME string = mcpSearchIndexFunctionApp.outputs.name
output AZURE_FUNCTIONAPP_MCP_FUNCTION_NAME string = 'event_grid_blob_trigger'
output USER_ASSIGNED_MANAGED_IDENTITY_ID string = userAssignedManagedIdentity.id
output AZURE_APPCONFIG_NAME string = appConfig.outputs.name

// AI Project outputs
output AI_PROJECT_NAME string = aiProject.outputs.projectName
output AI_PROJECT_ENDPOINT string = aiProject.outputs.projectEndpoint

output AZURE_STORAGE_ACCOUNT_NAME string = storageAccount.outputs.storageAccountName
output AZURE_SEARCH_SERVICE_NAME string = search.outputs.name
output AZURE_OPENAI_ENDPOINT string = cognitiveServices1.outputs.endpoint
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME string = openAIDeployments1.outputs.embeddingDeploymentName
// Expose the resolved naming prefix so post-deploy scripts (e.g., Event Grid subscription naming) can align
output EVENTGRID_RESOURCE_PREFIX string = prefix

// Bot Framework outputs
output BOT_SERVICE_NAME string = botService.outputs.botServiceName
output BOT_MESSAGING_ENDPOINT string = botService.outputs.messagingEndpoint
output BOT_TEAMS_CHANNEL_ENABLED bool = botService.outputs.teamsChannelEnabled
