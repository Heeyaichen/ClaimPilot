param location string
param projectName string
param environment string
param tags object = {}

var accountName = '${projectName}-${environment}-docintel'

resource docIntelligence 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: accountName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'FormRecognizer'
  properties: {
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

output docIntelligenceName string = docIntelligence.name
output docIntelligenceId string = docIntelligence.id
output docIntelligenceEndpoint string = docIntelligence.properties.endpoint
