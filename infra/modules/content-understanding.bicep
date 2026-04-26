param location string
param projectName string
param environment string
param tags object = {}

var accountName = '${projectName}-${environment}-cu'

resource contentUnderstanding 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: accountName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'CognitiveServices'
  properties: {
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

output contentUnderstandingName string = contentUnderstanding.name
output contentUnderstandingId string = contentUnderstanding.id
output contentUnderstandingEndpoint string = contentUnderstanding.properties.endpoint
