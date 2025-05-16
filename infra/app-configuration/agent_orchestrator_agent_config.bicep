param appConfigName string
param location string = resourceGroup().location
param identityId string // User-assigned managed identity resource ID

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: appConfigName
}

// Create variables for complex values
var orchestratorAgentConfig = {
  id: 'orchestrator_agent'
  name: 'Orchestrator Agent'
  description: 'Orchestrator agent is able to call other agents to delegate tasks.'
  systemPrompt: 'You are an orchestrator agent.\n\nYou will delegate tasks to other agents which you are able to call. Other agents have specific areas of responsibility. You may need to go back and forth a few times between agents to come to a conclusive answer.\n\nYou should always think first about what your plan will be, explain it, and then execute it. The user calling you doesn\'t want a long break, and wants to know what is going on.'
  defaultPrompts: [
    'Assess the impact of incoming deliveries. Show me the inventory for material \'MAT-HR-COIL\'. Use the location of the material, to get the weather forecast for the next 5 days. Use the weather forecast to help with your assessment analysis.'
    'What is the current weather in Orlando, FL?'
    'Show me the inbound deliveries for vendor STEEL-VEND-01'
    'Use the weather data with tile map layers with plotly js to display the weather by location on a map with html.'
  ]
  agentType: 'ChatCompletionAgent'
  foundryAgentId: ''
  modelSelection: {
    provider: 'AzureOpenAI'
    model: 'gpt-4o'
  }
  codeInterpreter: false
  fileUpload: false
  maxTurns: 10
  tools: [
    {
      type: 'Agent'
      id: 'sap_agent'
      name: 'SAP Agent'
      specUrl: ''
      authentications: [
        {
          type: 'Anonymous'
        }
      ]
    }
    {
      type: 'Agent'
      id: 'weather_agent'
      name: 'Weather Agent'
      specUrl: ''
      authentications: [
        {
          type: 'Anonymous'
        }
      ]
    }
  ]
  requireJsonResponse: false
  displayFunctionCallStatus: true
}

// Convert the object to a JSON string and encode it to base64 to avoid escaping issues
var orchestratorAgentConfigJson = base64(string(orchestratorAgentConfig))

resource deploymentScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'setAgentOrchestratorConfig-${uniqueString(appConfigName)}'
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
      CONFIG_BASE64=$2

      # Decode the base64 encoded config
      echo "$CONFIG_BASE64" | base64 -d > agent_config.json

      # Display content for debugging
      echo "Agent configuration JSON:"
      cat agent_config.json

      # Set the key-value in App Configuration
      echo "Setting agent:orchestrator_agent in App Configuration $APP_CONFIG_ENDPOINT"
      az appconfig kv set --endpoint "$APP_CONFIG_ENDPOINT" \
        --key "agent:orchestrator_agent" \
        --value @agent_config.json \
        --content-type "application/json" \
        --auth-mode login \
        --yes

      echo "Successfully set orchestrator agent config in $APP_CONFIG_ENDPOINT"
      
      # Verify the key was set
      echo "Verifying the key was set correctly:"
      az appconfig kv show --endpoint "$APP_CONFIG_ENDPOINT" --key "agent:orchestrator_agent" --query "key" || echo "Failed to verify key"
    '''
    arguments: '${appConfig.properties.endpoint} ${orchestratorAgentConfigJson}'
    cleanupPreference: 'OnSuccess'
  }
}

output orchestratorAgentConfigId string = 'agent:orchestrator_agent'
