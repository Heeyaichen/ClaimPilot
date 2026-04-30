param location string
param projectName string
param environment string
param tags object = {}

var registryName = '${take(projectName, 6)}${environment}acr${take(uniqueString(resourceGroup().id), 6)}'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: true
  }
  tags: tags
}

output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output acrId string = acr.id
