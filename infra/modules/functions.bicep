param location string
param projectName string
param environment string
param tags object = {}
param storageAccountName string
param storageAccountEndpoint string
// keyVaultEndpoint will be wired into app settings once secrets are stored
// param keyVaultEndpoint string

var functionAppName = '${projectName}-${environment}-func'
var planName = '${projectName}-${environment}-plan'

resource functionPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: planName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  kind: 'app'
  properties: {
    reserved: true
  }
  tags: tags
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: functionPlan.id
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccountName
        }
        {
          name: 'AzureWebJobsStorage'
          value: storageAccountEndpoint
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsFeatureFlags'
          value: 'EnableWorkerIndexing'
        }
      ]
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
}

output functionAppName string = functionApp.name
output functionAppId string = functionApp.id
output functionAppPrincipalId string = functionApp.identity.principalId
output functionPlanId string = functionPlan.id
output functionAppDefaultHostname string = functionApp.properties.defaultHostName
