param apiManagementServiceName string
param name string
param displayName string
param value string
param secret bool = false

resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apiManagementServiceName
}

resource namedValue 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = {
  parent: apim
  name: name
  properties: {
    displayName: displayName
    value: value
    tags: []
    secret: secret
  }
}

output id string = namedValue.id
