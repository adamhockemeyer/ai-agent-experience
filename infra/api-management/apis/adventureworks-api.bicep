@description('The name of the API Management instance to deploy this API to.')
param serviceName string
//param endpoint string

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: serviceName
}

var openApiSpecSwagger = loadTextContent('../openapi-specs/Adventureworks Products.openapi.yaml')

resource apiDefinition 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  name: 'adventureworks-products'
  parent: apimService
  properties: {
    path: 'products'
    description: ''
    displayName: 'Adventureworks Products'
    format: 'openapi'
    value: openApiSpecSwagger
    subscriptionRequired: true
    type: 'http'
    protocols: ['https']
    serviceUrl: '${apimService.properties.gatewayUrl}/products'
  }
}

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  name: 'policy'
  parent: apiDefinition
  properties: {
    format: 'rawxml'
    value: policy1
  }
}

var policy1 = '''
<policies>
    <!-- Throttle, authorize, validate, cache, or transform the requests -->
    <inbound>
        <base />
        <set-backend-service base-url="{{Adventureworks-API-Service-URL}}" />
    </inbound>
    <!-- Control if and how the requests are forwarded to services  -->
    <backend>
        <base />
    </backend>
    <!-- Customize the responses -->
    <outbound>
        <base />
    </outbound>
    <!-- Handle exceptions and customize error responses  -->
    <on-error>
        <base />
    </on-error>
</policies>
    '''

output id string = apiDefinition.id
