param location string
param projectName string
param environment string
param tags object = {}

var signalRName = '${projectName}-${environment}-signalr'

resource signalR 'Microsoft.SignalRService/signalR@2024-03-01' = {
  name: signalRName
  location: location
  sku: {
    name: 'Standard_S1'
    capacity: 1
  }
  properties: {
    tls: {
      clientCertEnabled: false
    }
    features: [
      {
        flag: 'ServiceMode'
        value: 'Default'
      }
    ]
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

output signalRName string = signalR.name
output signalRId string = signalR.id
output signalREndpoint string = signalR.properties.hostName
