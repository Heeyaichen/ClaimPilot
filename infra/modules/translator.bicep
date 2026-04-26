param location string
param projectName string
param environment string
param tags object = {}

var accountName = '${projectName}-${environment}-translator'

resource translator 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: accountName
  location: location
  sku: {
    name: 'S1'
  }
  kind: 'TextTranslation'
  properties: {
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

output translatorName string = translator.name
output translatorId string = translator.id
output translatorEndpoint string = translator.properties.endpoint
