param appConfigName string
param location string = resourceGroup().location
param identityId string // User-assigned managed identity resource ID
param sapFunctionAppName string // Name of the SAP function app, so we can get the URL and key

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: appConfigName
}

resource sapFunctionApp 'Microsoft.Web/sites@2024-04-01' existing = {
  name: sapFunctionAppName
}

// Create variables for complex values
var sapAgentConfig = {
  id: 'sap_agent'
  name: 'SAP Agent'
  description: 'Fetches information from our enterprise SAP system'
  systemPrompt: 'You are an SAP agent. \n\nYou will use the tools/functions available to you to get real-time information from our enterprise SAP ERP system. '
  defaultPrompts: [
    'Show me the inbound deliveries for vendor STEEL-VEND-01'
  ]
  agentType: 'ChatCompletionAgent'
  foundryAgentId: ''
  modelSelection: {
    provider: 'AzureOpenAI'
    model: 'gpt-4o'
  }
  codeInterpreter: false
  fileUpload: false
  maxTurns: 5
  tools: [
    {
      type: 'OpenAPI'
      id: 'tool_1'
      name: 'SAP Data API'
      specUrl: '${sapFunctionApp.properties.defaultHostName}/api/swagger.json'
      authentications: [
        {
          type: 'Header'
          headerName: 'x-functions-key'
          headerValue: sapFunctionApp.listKeys().keys[0].value
        }
      ]
    }
  ]
  requireJsonResponse: false
}

// Convert the object to a JSON string and encode it to base64 to avoid escaping issues
var sapAgentConfigJson = base64(string(sapAgentConfig))

resource deploymentScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'setAgentSapConfig-${uniqueString(appConfigName)}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    azCliVersion: '2.56.0'
    retentionInterval: 'P1D'
    timeout: 'PT5M'
    scriptContent: '''
      #!/bin/bash
      set -ex

      echo "Script started"

      APP_CONFIG_NAME=$1
      CONFIG_BASE64=$2

      # Decode the base64 encoded config
      echo "$CONFIG_BASE64" | base64 -d > agent_config.json

      # Display content for debugging
      echo "Agent configuration JSON:"
      cat agent_config.json

      # Set the key-value in App Configuration
      echo "Setting agent:sap_agent in App Configuration $APP_CONFIG_NAME"
      az appconfig kv set --name "$APP_CONFIG_NAME" \
        --key "agent:sap_agent" \
        --value @agent_config.json \
        --content-type "application/json" \
        --auth-mode login \
        --yes

      echo "Successfully set sap agent config in $APP_CONFIG_NAME"
      
      # Verify the key was set
      echo "Verifying the key was set correctly:"
      az appconfig kv show --name "$APP_CONFIG_NAME" --key "agent:sap_agent" --query "key" || echo "Failed to verify key"
    '''
    arguments: '${appConfigName} ${sapAgentConfigJson}'
    cleanupPreference: 'OnSuccess'
  }
}

output sapAgentConfigId string = 'agent:sap_agent'
