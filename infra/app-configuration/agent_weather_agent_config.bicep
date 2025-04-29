param appConfigName string
param apimName string
param apimSubscriptionName string = 'aiagent-subscription'
param location string = resourceGroup().location
param identityId string // User-assigned managed identity resource ID

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: appConfigName
}

resource apimService 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

resource apimSubscription 'Microsoft.ApiManagement/service/subscriptions@2023-09-01-preview' existing = {
  name: apimSubscriptionName
  parent: apimService
}

// Create variables for complex values
var weatherAgentConfig = {
  id: 'weather_agent'
  name: 'Weather Agent'
  description: 'Allows retrieving real-time weather information for a particular location.'
  systemPrompt: 'You are a Weather Agent.\n\nYou provide real-time weather information utilizing the tools available to you. Do not make up alternative sources or suggest alternative data sources.\n\nWhen making tool/function calls, ensure you understand the description of the arguments/properties. They may give useful information as to why types of values are allowed or required. For example, the \'query\' argument takes a latitude, longitude value, so you must convert a string location to this type.'
  defaultPrompts: [
    'What is the current weather in Orlando, FL?'
    'What is the forecast for the next 5 days in Seattle, WA? Can you show it in a table format.'
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
      name: 'Azure Maps Weather Service'
      specUrl: 'https://${apimName}.azure-api.net/docs/apis/azure-maps-weather-service?export=true&format=openapi&api-version=2022-08-01'
      authentications: [
        {
          type: 'Header'
          headerName: 'Ocp-Apim-Subscription-Key'
          headerValue: '' // Will be set in the script
        }
      ]
    }
  ]
  requireJsonResponse: false
  displayFunctionCallStatus: true
}

// Convert the object to a JSON string and encode it to base64 to avoid escaping issues
var weatherAgentConfigJson = base64(string(weatherAgentConfig))

resource deploymentScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'setAgentWeatherConfig-${uniqueString(appConfigName)}'
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

      APP_CONFIG_ENDPOINT=$1
      APIM_NAME=$2
      SUBSCRIPTION_KEY=$3
      CONFIG_BASE64=$4

      echo "Using provided subscription key"

      # Decode the base64 encoded config
      echo "$CONFIG_BASE64" | base64 -d > agent_config.json

      # Update the subscription key in the config
      python3 -c "
import json
import sys

# Load the JSON
with open('agent_config.json', 'r') as f:
    config = json.load(f)

# Update the subscription key
config['tools'][0]['authentications'][0]['headerValue'] = '$SUBSCRIPTION_KEY'

# Write back the updated JSON
with open('agent_config.json', 'w') as f:
    json.dump(config, f)
"

      # Display content for debugging
      echo "Agent configuration JSON:"
      cat agent_config.json

      # Set the key-value in App Configuration
      echo "Setting agent:weather_agent in App Configuration $APP_CONFIG_ENDPOINT"
      az appconfig kv set --endpoint "$APP_CONFIG_ENDPOINT" \
        --key "agent:weather_agent" \
        --value @agent_config.json \
        --content-type "application/json" \
        --auth-mode login \
        --yes

      echo "Successfully set weather agent config in $APP_CONFIG_ENDPOINT"
      
      # Verify the key was set
      echo "Verifying the key was set correctly:"
      az appconfig kv show --endpoint "$APP_CONFIG_ENDPOINT" --key "agent:weather_agent" --query "key" || echo "Failed to verify key"
    '''
    arguments: '${appConfig.properties.endpoint} ${apimName} ${apimSubscription.listSecrets().primaryKey} ${weatherAgentConfigJson}'
    cleanupPreference: 'OnSuccess'
  }
}

output weatherAgentConfigId string = 'agent:weather_agent'
