// Import Microsoft Graph Bicep extension
extension microsoftGraphV1

@description('Name of the Bot Service resource')
param botName string

@description('Display name for the bot')
param botDisplayName string = botName

@description('Description of the bot')
param botDescription string = 'AI Agent Bot for Microsoft Teams and Copilot integration'

@description('Bot messaging endpoint URL')
param messagingEndpoint string

@description('Common tags to apply to all resources')
param commonTags object = {}

@description('Unique suffix for resources')
var uniqueSuffix = substring(uniqueString(resourceGroup().id), 0, 8)

// Create a valid uniqueName (alphanumeric only, no spaces or special chars)
var appUniqueName = 'aiagentbot${uniqueSuffix}'

// Create App Registration using Microsoft Graph Bicep extension
resource appRegistration 'Microsoft.Graph/applications@v1.0' = {
  displayName: '${botDisplayName} App'
  signInAudience: 'AzureADMyOrg' // Single-tenant
  uniqueName: appUniqueName
  web: {
    redirectUris: [
      'https://token.botframework.com/.auth/web/redirect'
    ]
  }
  requiredResourceAccess: [
    {
      resourceAppId: '00000003-0000-0000-c000-000000000000' // Microsoft Graph
      resourceAccess: [
        {
          id: 'e1fe6dd8-ba31-4d61-89e7-88639da4683d' // User.Read
          type: 'Scope'
        }
      ]
    }
  ]
}

// Create the Bot Service resource
resource botService 'Microsoft.BotService/botServices@2022-09-15' = {
  name: botName
  location: 'global' // Bot Service is always global
  tags: commonTags
  sku: {
    name: 'F0' // Free tier
  }
  kind: 'azurebot'
  properties: {
    displayName: botDisplayName
    description: botDescription
    endpoint: messagingEndpoint
    msaAppType: 'SingleTenant'
    msaAppId: appRegistration.appId
    msaAppTenantId: tenant().tenantId
    schemaTransformationVersion: '1.3'
    isCmekEnabled: false
    isStreamingSupported: true
    openWithHint: 'bfcomposer://open'
    manifestUrl: '${messagingEndpoint}/api/messages/manifest'
  }
}

// Add Microsoft Teams channel
resource teamsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: botService
  name: 'MsTeamsChannel'
  location: 'global'
  properties: {
    channelName: 'MsTeamsChannel'
    properties: {
      isEnabled: true
      enableCalling: false
    }
  }
}

// Add Direct Line channel for web chat
resource directLineChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: botService
  name: 'DirectLineChannel'
  location: 'global'
  properties: {
    channelName: 'DirectLineChannel'
    properties: {
      sites: [
        {
          siteName: 'Default Site'
          isEnabled: true
          isV1Enabled: true
          isV3Enabled: true
        }
      ]
    }
  }
}

@description('Bot Service resource ID')
output botServiceId string = botService.id

@description('Bot Service name')
output botServiceName string = botService.name

@description('Microsoft App ID for the bot')
output microsoftAppId string = appRegistration.appId

@description('Microsoft App Object ID')
output microsoftAppObjectId string = appRegistration.id

@description('Microsoft App Tenant ID')
output microsoftAppTenantId string = tenant().tenantId

// Note: Client secret must be created manually or via separate script
// Microsoft Graph Bicep templates don't support passwordCredentials yet
@description('Client secret placeholder - must be created manually')
output microsoftAppSecretRequired string = 'Please create client secret manually for App ID: ${appRegistration.appId}'

@description('Bot messaging endpoint')
output messagingEndpoint string = messagingEndpoint

@description('Teams channel configuration')
output teamsChannelEnabled bool = true

@description('Direct Line channel configuration')
output directLineChannelEnabled bool = true
