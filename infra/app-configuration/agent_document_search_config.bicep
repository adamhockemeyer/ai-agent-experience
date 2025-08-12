param appConfigName string
param functionAppName string
param location string = resourceGroup().location
param identityId string // User-assigned managed identity resource ID

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: appConfigName
}

// Compose the config key and URL
var documentSearchUrl = 'https://${functionAppName}.azurewebsites.net/runtime/webhooks/mcp/sse'
var configKey = 'agents:document_search_agent'

// Full agent configuration with placeholder mcpDefinition; we'll inject URL and key in the script
var documentSearchAgentConfig = {
  id: 'document_search_agent'
  name: 'Document Search Agent'
  description: 'Uses tools to search through indexed documents to find relevant information to a request.'
  systemPrompt: 'You are a document search agent. You have tools available to search for information in documents for a users request.\n\nIf a url to a document is include, ensure it is returned in full form and any query strings are not stripped off.'
  defaultPrompts: [
    'Talstar mixing ratios and dilution instructions'
    'What insects does Talstar target?'
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
      name: 'Document Search'
      specUrl: ''
      mcpDefinition: '{\n  "mcpServers": {\n    "documentSearch": {\n      "type": "sse", \n      "url": "__URL__",\n      "auth": {\n        "headers": {\n          "x-functions-key": "__KEY__"\n        }\n      }\n    }\n  }\n}'
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

// Base64 encode to avoid escaping issues when passing to the script
var documentSearchAgentConfigJson = base64(string(documentSearchAgentConfig))

resource deploymentScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'setDocumentSearchConfig-${uniqueString(appConfigName)}'
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
  set -euo pipefail
  set -x
      
      APP_CONFIG_ENDPOINT=$1
      FUNCTION_APP_NAME=$2
      CONFIG_KEY=$3
      DOCUMENT_SEARCH_URL=$4
  SUBSCRIPTION_ID=$5
  RESOURCE_GROUP_NAME=$6
  CONFIG_BASE64=$7
      
      # Retrieve system key with retries (propagation/permission delays)
      SYSTEM_KEY=""
      for attempt in 1 2 3 4 5; do
        SYSTEM_KEY=$(az functionapp keys list \
          --name "$FUNCTION_APP_NAME" \
          --resource-group "$RESOURCE_GROUP_NAME" \
          --query "systemKeys.mcp_extension" -o tsv 2>/dev/null || true)
        if [ -n "$SYSTEM_KEY" ]; then
          break
        fi
        sleep $((attempt*2))
      done

      if [ -z "$SYSTEM_KEY" ]; then
        SYSTEM_KEY=$(az rest --method post --uri \
          "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME/host/default/listkeys?api-version=2023-01-01" \
          --query "systemKeys.mcp_extension" -o tsv 2>/dev/null || true)
      fi
      
      if [ -z "$SYSTEM_KEY" ]; then
        echo "Failed to retrieve mcp_extension system key. Dumping available system keys for diagnostics:"
        az functionapp keys list --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP_NAME" -o json || true
        exit 1
      fi
      
    # Decode the base64-encoded agent config template
    echo "$CONFIG_BASE64" | base64 -d > agent_config.json

  # Replace placeholders in-place (mcpDefinition stays a JSON string containing URL & key)
  sed -e "s|__URL__|$DOCUMENT_SEARCH_URL|g" -e "s|__KEY__|$SYSTEM_KEY|g" agent_config.json > agent_config.tmp && mv agent_config.tmp agent_config.json

  echo "Final agent_config.json after placeholder substitution:" >&2
  cat agent_config.json >&2
      
      # Set the key-value in App Configuration
      az appconfig kv set --endpoint "$APP_CONFIG_ENDPOINT" \
        --key "$CONFIG_KEY" \
  --value @agent_config.json \
        --content-type "application/json" \
        --auth-mode login \
        --yes
      
      echo "Successfully set $CONFIG_KEY in $APP_CONFIG_ENDPOINT"
      
      # Verify the key was set
      az appconfig kv show --endpoint "$APP_CONFIG_ENDPOINT" --key "$CONFIG_KEY" --query "key" || echo "Failed to verify key"
    '''
    arguments: '${appConfig.properties.endpoint} ${functionAppName} ${configKey} ${documentSearchUrl} ${subscription().subscriptionId} ${resourceGroup().name} ${documentSearchAgentConfigJson}'
    cleanupPreference: 'OnSuccess'
    forceUpdateTag: uniqueString(appConfigName, functionAppName)
    environmentVariables: []
    // Windows support
    primaryScriptUri: ''
  }
}

output documentSearchConfigKey string = configKey
