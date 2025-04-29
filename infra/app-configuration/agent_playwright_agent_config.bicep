param appConfigName string
param location string = resourceGroup().location
param identityId string // User-assigned managed identity resource ID

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: appConfigName
}

// Create variables for complex values
var playwrightAgentConfig = {
  id: 'playwright_agent'
  name: 'Playwright Agent'
  description: 'Playwright agent uses MCP to have the Playwright agent execute tasks.'
  systemPrompt: 'You are a Playwright agent, which specializes at browser automation tasks. Use the tools available to you to perform actions as needed.'
  defaultPrompts: [
    'Can you get me the top 3 results for controlling chinch bugs from https://www.domyown.com'
    'Can you get more details on the first item, and display it in table format?'
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
      type: 'ModelContextProtocol'
      id: 'tool_1'
      name: 'Playwright MCP'
      specUrl: ''
      mcpDefinition: '{\n  "mcpServers": {\n    "playwright": {\n      "command": "npx",\n      "args": [\n        "@playwright/mcp@latest",\n        "--headless"\n      ]\n    }\n  }\n}'
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
var playwrightAgentConfigJson = base64(string(playwrightAgentConfig))

resource deploymentScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'setAgentPlaywrightConfig-${uniqueString(appConfigName)}'
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
      echo "Setting agent:playwright_agent in App Configuration $APP_CONFIG_ENDPOINT"
      az appconfig kv set --endpoint "$APP_CONFIG_ENDPOINT" \
        --key "agent:playwright_agent" \
        --value @agent_config.json \
        --content-type "application/json" \
        --auth-mode login \
        --yes

      echo "Successfully set playwright agent config in $APP_CONFIG_ENDPOINT"
      
      # Verify the key was set
      echo "Verifying the key was set correctly:"
      az appconfig kv show --endpoint "$APP_CONFIG_ENDPOINT" --key "agent:playwright_agent" --query "key" || echo "Failed to verify key"
    '''
    arguments: '${appConfig.properties.endpoint} ${playwrightAgentConfigJson}'
    cleanupPreference: 'OnSuccess'
  }
}

output playwrightAgentConfigId string = 'agent:playwright_agent'
