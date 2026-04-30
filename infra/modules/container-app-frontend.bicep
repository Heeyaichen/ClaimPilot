param location string
param projectName string
param environment string
param tags object = {}
param environmentId string
param acrLoginServer string
param imageName string
param apiBaseUrl string

var appName = '${projectName}-${environment}-frontend'

resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3000
        transport: 'http'
        allowInsecure: true
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${acrLoginServer}/${imageName}'
          env: [
            { name: 'NEXT_PUBLIC_API_BASE_URL', value: apiBaseUrl }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
}

output frontendAppName string = frontendApp.name
output frontendFqdn string = frontendApp.properties.configuration.ingress.fqdn
