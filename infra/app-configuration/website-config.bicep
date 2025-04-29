param appConfigName string
param websiteName string = 'AI Agent Experience'
param authenticationEnabled bool = false
param openAIDeployments array
param location string = resourceGroup().location
param identityId string // User-assigned managed identity resource ID

// Base64 encode the deployments array for safe script passing
var deploymentsBase64 = base64(string(openAIDeployments))

resource appConfig 'Microsoft.AppConfiguration/configurationStores@2024-05-01' existing = {
  name: appConfigName
}

resource deploymentScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'setWebsiteConfig-${uniqueString(appConfigName)}'
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
      set -e

      APP_CONFIG_ENDPOINT=$1
      WEBSITE_NAME=$2
      AUTH_ENABLED=$3
      DEPLOYMENTS_BASE64=$4

      # Decode deployments array
      echo "$DEPLOYMENTS_BASE64" | base64 -d > deployments.json

      # Validate JSON
      if ! jq empty deployments.json; then
        echo "ERROR: deployments.json is not valid JSON"
        cat deployments.json
        exit 1
      fi

      # Filter out embedding models and build modelMappings
      jq '[.[] | select(.model | contains("embedding") | not) | 
        {
          agentType: "ChatCompletionAgent",
          provider: "AzureOpenAI",
          model: .model,
          displayName: .name,
          enabled: true,
          id: ("model_" + (.name | gsub("[^a-zA-Z0-9]";"") | .[0:8]))
        }
      ]' deployments.json > modelMappings.json

      # Remove nulls (from second mapping if not all models have both types)
      jq '[.[] | select(.model != null)]' modelMappings.json > modelMappingsClean.json

      # Build the final config JSON
      jq -n \
        --arg name "$WEBSITE_NAME" \
        --argjson authEnabled $AUTH_ENABLED \
        --slurpfile modelMappings modelMappingsClean.json \
        '{
          name: $name,
          authenticationEnabled: $authEnabled,
          modelMappings: $modelMappings[0],
          menuHiddenAgentIds: []
        }' > config.json

      # Debug output
      echo "Final config.json:"
      cat config.json

      # Set the key-value in App Configuration
      az appconfig kv set --endpoint "$APP_CONFIG_ENDPOINT" \
        --key "website" \
        --value @config.json \
        --content-type "application/json" \
        --auth-mode login \
        --yes

      echo "Successfully set website config in $APP_CONFIG_ENDPOINT"
    '''
    arguments: '${appConfig.properties.endpoint} "${websiteName}" ${toLower(string(authenticationEnabled))} ${deploymentsBase64}'
    cleanupPreference: 'OnSuccess'
  }
}

output websiteConfigId string = 'website'
