
param baseName string

param tags object = {}

// ---- New resources ----

#disable-next-line BCP081
resource bingAccount 'Microsoft.Bing/accounts@2025-05-01-preview' = {
  name: 'bing-ai-agent-${baseName}'
  location: 'global'
  kind: 'Bing.Grounding'
  sku: {
    name: 'G1'
  }
  tags: tags
}

// ---- Outputs ----

output bingAccountName string = bingAccount.name
