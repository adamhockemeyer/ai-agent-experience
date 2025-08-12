@description('Resource name prefix')
param prefix string

@description('Azure region where resources should be deployed')
param location string

@description('Storage account resource ID')
param storageAccountId string

@description('MCP Azure Function Event Grid trigger URL for Event Grid subscription (e.g. https://<functionapp>.azurewebsites.net/runtime/webhooks/eventgrid?functionName=<functionName>&code=<key>)')
param mcpFunctionEventGridUrl string

@description('User assigned managed identity resource ID')
param userAssignedManagedIdentityId string

// Script to handle Event Grid system topic and subscription creation
resource createEventGridResources 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'createEventGrid-${uniqueString(storageAccountId)}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedManagedIdentityId}': {}
    }
  }
  properties: {
    azCliVersion: '2.50.0'
    scriptContent: '''
      echo "=== Managing Event Grid system topic and subscription ==="

      STORAGE_ACCOUNT_ID="${STORAGE_ACCOUNT_ID}"
      PREFIX="${PREFIX}"
      LOCATION="${LOCATION}"
      MCP_FUNCTION_EVENTGRID_URL="${MCP_FUNCTION_EVENTGRID_URL}"

      # Extract resource group and storage name
      resource_group=$(echo "${STORAGE_ACCOUNT_ID}" | cut -d'/' -f5)
      storage_name=$(echo "${STORAGE_ACCOUNT_ID}" | rev | cut -d'/' -f1 | rev)

      echo "Storage Account: ${storage_name}"
      echo "Resource Group: ${resource_group}"
      echo "Original Storage Account ID: ${STORAGE_ACCOUNT_ID}"
      echo "MCP Function Event Grid URL: ${MCP_FUNCTION_EVENTGRID_URL}"

      # Step 1: Find or create system topic
      echo "=== Step 1: Finding or creating system topic ==="
      system_topic_name="${storage_name}-${RANDOM}-systemtopic"
      # Try to find existing system topic for this storage account
      all_topics=$(az eventgrid system-topic list --resource-group "${resource_group}" --output json)
      existing_topic=$(echo "${all_topics}" | jq --arg storage_name "${storage_name}" '[.[] | select(.source | contains($storage_name))] | .[0]')
      if [ "${existing_topic}" != "null" ] && [ "${existing_topic}" != "" ]; then
        topic_name=$(echo "${existing_topic}" | jq -r '.name')
        topic_id=$(echo "${existing_topic}" | jq -r '.id')
        echo "Found existing system topic: ${topic_name}"
        echo "Topic ID: ${topic_id}"
      else
        # Create system topic
        topic_name="${PREFIX}-systemtopic"
        echo "No existing system topic found. Creating: ${topic_name}"
        create_topic_result=$(az eventgrid system-topic create \
          --name "${topic_name}" \
          --resource-group "${resource_group}" \
          --location "${LOCATION}" \
          --topic-type Microsoft.Storage.StorageAccounts \
          --source "${STORAGE_ACCOUNT_ID}" \
          --output json 2>&1)
        if [ $? -eq 0 ]; then
          topic_id=$(echo "${create_topic_result}" | jq -r '.id')
          echo "Successfully created system topic: ${topic_name}"
        else
          echo "Failed to create system topic:"
          echo "${create_topic_result}"
          exit 1
        fi
      fi

      # Step 2: Create event subscription
      subscription_name="${PREFIX}-mcp-search-index-subscription"
      echo "Creating event subscription: ${subscription_name}"

      # Check for existing subscription
      all_subs=$(az eventgrid system-topic event-subscription list --resource-group "${resource_group}" --system-topic-name "${topic_name}" --output json)
      existing_sub=$(echo "${all_subs}" | jq --arg subscription_name "${subscription_name}" '[.[] | select(.name == $subscription_name)] | .[0]')
      if [ "${existing_sub}" != "null" ] && [ "${existing_sub}" != "" ]; then
        sub_id=$(echo "${existing_sub}" | jq -r '.id')
        echo "Found existing subscription: ${subscription_name}"
      else
        # Create new subscription
        echo "Creating subscription with Azure Function endpoint..."
        echo "Function Event Grid URL: ${MCP_FUNCTION_EVENTGRID_URL}"
        result=$(az eventgrid system-topic event-subscription create \
          --name "${subscription_name}" \
          --resource-group "${resource_group}" \
          --system-topic-name "${topic_name}" \
          --endpoint "${MCP_FUNCTION_EVENTGRID_URL}" \
          --endpoint-type webhook \
          --subject-begins-with "/blobServices/default/containers/documents/" \
          --included-event-types Microsoft.Storage.BlobCreated Microsoft.Storage.BlobDeleted \
          --output json 2>&1)
        if [ $? -eq 0 ]; then
          sub_id=$(echo "${result}" | jq -r '.id')
          echo "Successfully created subscription: ${subscription_name}"
        else
          echo "Failed to create subscription:"
          echo "${result}"
          exit 1
        fi
      fi

      # Output results
      echo "{\"topicName\": \"${topic_name}\", \"topicId\": \"${topic_id}\", \"subscriptionName\": \"${subscription_name}\", \"subscriptionId\": \"${sub_id}\"}" > $AZ_SCRIPTS_OUTPUT_PATH
    '''
    environmentVariables: [
      { name: 'STORAGE_ACCOUNT_ID', value: storageAccountId }
      { name: 'PREFIX', value: prefix }
      { name: 'LOCATION', value: location }
      { name: 'MCP_FUNCTION_EVENTGRID_URL', value: mcpFunctionEventGridUrl }
      { name: 'MANAGED_IDENTITY_ID', value: userAssignedManagedIdentityId }
    ]
    timeout: 'PT10M'
    retentionInterval: 'PT1H'
  }
}

// Output the results
output systemTopicName string = createEventGridResources.properties.outputs.topicName
output systemTopicId string = createEventGridResources.properties.outputs.topicId
output subscriptionName string = createEventGridResources.properties.outputs.subscriptionName
output subscriptionId string = createEventGridResources.properties.outputs.subscriptionId
