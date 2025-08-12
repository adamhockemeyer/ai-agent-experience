@description('Resource name prefix')
param prefix string

@description('Azure region where resources should be deployed')
param location string

@description('Storage account resource ID')
param storageAccountId string

@description('MCP Azure Function resource ID for Event Grid subscription')
param mcpFunctionResourceId string

@description('Dead letter storage account resource ID')
param deadLetterStorageAccountId string

@description('Dead letter blob container name')
param deadLetterContainerName string = 'eventgrid-deadletter'

@description('Existing system topic name if one already exists for the storage account. Leave empty to create new.')
param existingSystemTopicName string = ''

// Extract storage account name for system topic naming
var storageAccountName = last(split(storageAccountId, '/'))
var newSystemTopicName = '${prefix}-${storageAccountName}-systemtopic'
// Use a fixed subscription name for simplicity across environments
var subscriptionName = 'mcp-search-index-subscription'
var useExistingTopic = !empty(existingSystemTopicName)

// Reference existing system topic if specified
resource existingSystemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' existing = if (useExistingTopic) {
  name: existingSystemTopicName
}

// Create new system topic only if no existing topic name provided
resource newSystemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = if (!useExistingTopic) {
  name: newSystemTopicName
  location: location
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

// Create Event Grid subscription for existing topic
resource eventSubscriptionExisting 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = if (useExistingTopic) {
  parent: existingSystemTopic
  name: subscriptionName
  properties: {
    destination: {
      endpointType: 'AzureFunction'
      properties: {
        resourceId: mcpFunctionResourceId
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    filter: {
      subjectBeginsWith: '/blobServices/default/containers/documents/'
      subjectEndsWith: ''
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
        'Microsoft.Storage.BlobDeleted'
      ]
      enableAdvancedFilteringOnArrays: true
    }
    deadLetterDestination: {
      endpointType: 'StorageBlob'
      properties: {
        resourceId: deadLetterStorageAccountId
        blobContainerName: deadLetterContainerName
      }
    }
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
    eventDeliverySchema: 'EventGridSchema'
  }
}

// Create Event Grid subscription for new topic
resource eventSubscriptionNew 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = if (!useExistingTopic) {
  parent: newSystemTopic
  name: subscriptionName
  properties: {
    destination: {
      endpointType: 'AzureFunction'
      properties: {
        resourceId: mcpFunctionResourceId
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    filter: {
      subjectBeginsWith: '/blobServices/default/containers/documents/'
      subjectEndsWith: ''
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
        'Microsoft.Storage.BlobDeleted'
      ]
      enableAdvancedFilteringOnArrays: true
    }
    deadLetterDestination: {
      endpointType: 'StorageBlob'
      properties: {
        resourceId: deadLetterStorageAccountId
        blobContainerName: deadLetterContainerName
      }
    }
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
    eventDeliverySchema: 'EventGridSchema'
  }
}

// Outputs - conditionally reference the appropriate resources
output systemTopicName string = useExistingTopic ? existingSystemTopic.name : newSystemTopic.name
output systemTopicId string = useExistingTopic ? existingSystemTopic.id : newSystemTopic.id
output subscriptionName string = useExistingTopic ? eventSubscriptionExisting.name : eventSubscriptionNew.name
output subscriptionId string = useExistingTopic ? eventSubscriptionExisting.id : eventSubscriptionNew.id
output systemTopicResourceId string = useExistingTopic ? existingSystemTopic.id : newSystemTopic.id
output isUsingExistingTopic bool = useExistingTopic
