@description('The name of the API Management instance to deploy this API to.')
param serviceName string

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: serviceName
}

var api = {
  title: 'Azure Maps Weather Service'
  name: 'azure-maps-weather-service'
  description: 'Azure Maps Weather Service provides real-time weather data for a given location.'
  path: 'weather'
  openapispec: 'https://raw.githubusercontent.com/Azure/azure-rest-api-specs/refs/heads/main/specification/maps/data-plane/Microsoft.Maps/Weather/preview/1.0/weather.json'
}

resource apiDefinitions 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  name: api.name
  parent: apimService
  properties: {
    path: api.path
    description: api.description
    displayName: api.title
    format: 'swagger-link-json'
    value: api.openapispec
    subscriptionRequired: true
    type: 'http'
    protocols: ['https']
    serviceUrl: 'https://atlas.microsoft.com'
  }
}

var policy = '''
<policies>
    <!-- Throttle, authorize, validate, cache, or transform the requests -->
    <inbound>
        <base />
        <authentication-managed-identity resource="https://atlas.microsoft.com/" output-token-variable-name="managed-id-access-token" ignore-error="false" />
        <set-header name="Authorization" exists-action="override">
            <value>@("Bearer " + (string)context.Variables["managed-id-access-token"])</value>
        </set-header>
        <set-header name="x-ms-client-id" exists-action="override">
            <value>{{Azure-Maps-Client-ID}}</value>
        </set-header>
        <set-query-parameter name="unit" exists-action="override">
            <value>imperial</value>
        </set-query-parameter>
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

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  name: 'policy'
  parent: apiDefinitions
  properties: {
    format: 'rawxml'
    value: policy
  }
}

output id string = apiDefinitions.id
