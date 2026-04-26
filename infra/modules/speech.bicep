param location string
param projectName string
param environment string
param tags object = {}

var accountName = '${projectName}-${environment}-speech'

resource speechService 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: accountName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'SpeechServices'
  properties: {
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

output speechServiceName string = speechService.name
output speechServiceId string = speechService.id
output speechServiceEndpoint string = speechService.properties.endpoint
