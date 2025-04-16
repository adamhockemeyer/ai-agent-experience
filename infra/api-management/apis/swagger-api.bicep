@description('The name of the API Management instance to deploy this API to.')
param serviceName string
//param endpoint string

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: serviceName
}

var openApiSpecSwagger = loadTextContent('../openapi-specs/Swagger API.openapi.yaml')

resource apiDefinition 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  name: 'swagger-api'
  parent: apimService
  properties: {
    path: 'docs'
    description: 'OpenAPI specs and utility APIs for Azure Management Rest API operations'
    displayName: 'swagger-api'
    format: 'openapi'
    value: openApiSpecSwagger
    subscriptionRequired: true
    type: 'http'
    protocols: ['https']
    serviceUrl: '${apimService.properties.gatewayUrl}/docs'
  }
}

module namedValueAPIMServiceUrl '../apim-namevalue.bicep' = {
  name: 'named-value-apim-service-url'
  params: {
    apiManagementServiceName: apimService.name
    name: 'apim-management-service-url'
    displayName: 'APIM-Management-Service-URL'
    value: 'https://management.azure.com/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.ApiManagement/service/${apimService.name}'
  }
}

// resource operationOpenAPISpec 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' existing = {
//   name: 'openapi-spec'
//   parent: apiDefinition
// }

// resource operationPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = {
//   parent: operationOpenAPISpec
//   name: 'policy'
//   properties: {
//     format: 'rawxml'
//     value: policy1
//   }
// }

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
    <inbound>
        <base />
        <set-backend-service base-url="{{APIM-Management-Service-URL}}" />
        <authentication-managed-identity resource="https://management.azure.com/" />
        <cache-lookup vary-by-developer="true" vary-by-developer-groups="true" allow-private-response-caching="true" must-revalidate="true" downstream-caching-type="none" />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
        <cache-store duration="30" cache-response="true" />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
    '''

output id string = apiDefinition.id
