param apiManagementServiceName string
param productName string
param productDisplayName string
param productDescription string
param productTerms string
param subscriptionRequired bool = true
param approvalRequired bool = false
param subscriptionsLimit int = 1
param state string = 'published'
param productApis array = []

resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apiManagementServiceName
}

resource product 'Microsoft.ApiManagement/service/products@2024-06-01-preview' = {
  parent: apim
  name: productName
  properties: {
    displayName: productDisplayName
    description: productDescription
    terms: productTerms
    subscriptionRequired: subscriptionRequired
    approvalRequired: approvalRequired
    subscriptionsLimit: subscriptionsLimit
    state: state
    
  }
}

resource productsApis 'Microsoft.ApiManagement/service/products/apiLinks@2024-06-01-preview' =  [
  for api in productApis: if (length(productApis) > 0) {
  parent: product
  name: uniqueString(api)
  properties: {
    apiId: api
  }
}]

output productName string = product.name
output productDisplayName string = product.properties.displayName
