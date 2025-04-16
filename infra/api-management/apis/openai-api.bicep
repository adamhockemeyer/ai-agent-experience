@description('The name of the API Management instance to deploy this API to.')
param serviceName string
//param endpoint string
param backendName string
param apimLoggerName string

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: serviceName
}

//var openApiSpecUrl = 'https://raw.githubusercontent.com/Azure/azure-rest-api-specs/main/specification/cognitiveservices/data-plane/AzureOpenAI/inference/stable/2024-10-21/inference.json'
var openApiSpecUrl = 'https://raw.githubusercontent.com/Azure/azure-rest-api-specs/refs/heads/main/specification/cognitiveservices/data-plane/AzureOpenAI/inference/preview/2024-12-01-preview/inference.json'
// var aoaiSwagger = loadTextContent('./azure-openai-2024-10-21.json')
// var aoaiSwaggerUrl = replace(aoaiSwagger, 'https://{endpoint}/openai', 'https://${endpoint}/openai')
// var aoaiSwaggerDefault = replace(aoaiSwaggerUrl, 'your-resource-name.openai.azure.com', '${serviceName}')

resource apiDefinition 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  name: 'azure-openai'
  parent: apimService
  properties: {
    path: 'openai'
    description: 'See https://raw.githubusercontent.com/Azure/azure-rest-api-specs/refs/heads/main/specification/cognitiveservices/data-plane/AzureOpenAI/inference/preview/2024-12-01-preview/inference.json'
    displayName: 'azure-openai'
    format: 'openapi-link'
    value: openApiSpecUrl
    subscriptionRequired: true
    type: 'http'
    protocols: ['https']
  }
}

var policy1 = '''
    <policies>
      <inbound>
        <base />
      <choose>
          <!-- If we are calling the Assistants API, we can't load balance since all of the Assistant objects are scoped to a single instance of OpenAI-->
          <when condition="@(context.Request.Url.Path.Contains("assistants") || context.Request.Url.Path.Contains("threads"))">
              <set-backend-service backend-id="{{non-load-balanced-openai-backend-name}}" />
          </when>
          <otherwise>
              <set-backend-service backend-id="{{OpenAI-Backend-Pool}}" />
          </otherwise>
      </choose> 
      <authentication-managed-identity resource="https://cognitiveservices.azure.com" output-token-variable-name="managed-id-access-token" ignore-error="false" />
      <set-header name="Authorization" exists-action="override">
          <value>@("Bearer " + (string)context.Variables["managed-id-access-token"])</value>
      </set-header>
      <!-- <azure-openai-token-limit counter-key="@(context.Subscription.Id)" tokens-per-minute="150000" estimate-prompt-tokens="true" tokens-consumed-header-name="x-request-tokens-consumed" tokens-consumed-variable-name="tokensConsumed" remaining-tokens-variable-name="remainingTokens" /> -->
      <azure-openai-emit-token-metric namespace="openai">
            <dimension name="Subscription ID" value="@(context.Subscription.Id)" />
            <dimension name="Client IP" value="@(context.Request.IpAddress)" />
            <dimension name="API ID" value="@(context.Api.Id)" />
            <dimension name="User ID" value="@(context.Request.Headers.GetValueOrDefault("x-user-id", "N/A"))" />
        </azure-openai-emit-token-metric>
      </inbound>
      <backend>
        <!--Set count to one less than the number of backends in the pool to try all backends until the backend pool is temporarily unavailable.-->
        <retry count="2" interval="0" first-fast-retry="true" condition="@(context.Response.StatusCode == 429 || (context.Response.StatusCode == 503 && !context.Response.StatusReason.Contains("Backend pool") && !context.Response.StatusReason.Contains("is temporarily unavailable")))">
            <forward-request buffer-request-body="true" />
        </retry>
      </backend>
      <outbound>
        <base />
        <emit-metric name="LLMCall" value="1" namespace="openai">
            <dimension name="API ID" />
            <dimension name="llm-backend" value="@(context.Request.Url.Scheme + "://" + context.Request.Url.Host + context.Api.Path)" />
            <dimension name="llm-region" value="@(context.Response.Headers.GetValueOrDefault("x-ms-region", ""))" />
        </emit-metric>
        <set-header name="x-backend" exists-action="override">
            <value>@(context.Request.Url.Scheme + "://" + context.Request.Url.Host + context.Api.Path)</value>
        </set-header>
      </outbound>
      <on-error>
        <base />
      </on-error>
    </policies>
    '''

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  name: 'policy'
  parent: apiDefinition
  properties: {
    format: 'rawxml'
    value: policy1
  }
}

var logSettings = {
  headers: [
    'Content-type'
    'User-agent'
    'x-ms-region'
    'x-ratelimit-remaining-tokens'
    'x-ratelimit-remaining-requests'
  ]
  body: { bytes: 8192 }
}

resource apimLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' existing = if (!empty(apimLoggerName)) {
  name: apimLoggerName
  parent: apimService
}

resource apiDiagnostics 'Microsoft.ApiManagement/service/apis/diagnostics@2022-08-01' = if (!empty(apimLogger.name)) {
  name: 'applicationinsights'
  parent: apiDefinition
  properties: {
    alwaysLog: 'allErrors'
    httpCorrelationProtocol: 'W3C'
    logClientIp: true
    loggerId: apimLogger.id
    metrics: true
    verbosity: 'verbose'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: logSettings
      response: logSettings
    }
    backend: {
      request: logSettings
      response: logSettings
    }
  }
}

output id string = apiDefinition.id
