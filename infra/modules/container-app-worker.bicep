param location string
param projectName string
param environment string
param tags object = {}
param environmentId string
param acrLoginServer string
param imageName string
param storageEndpoint string
param cosmosEndpoint string
param cosmosDatabaseName string
param serviceBusNamespaceName string
param claimsIngestionQueueName string
param signalREndpoint string
param searchEndpoint string = ''
param keyVaultEndpoint string
param docIntelligenceEndpoint string
param speechEndpoint string
param translatorEndpoint string
param translatorRegion string = 'swedencentral'
param contentUnderstandingEndpoint string
param foundryProjectEndpoint string = ''
param modelDeploymentName string = 'gpt-5-4'
param claimpilotUseStubs bool = true
param docIntelligenceModelId string = 'prebuilt-document'

var appName = '${projectName}-${environment}-worker'

resource workerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
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
          name: 'worker'
          image: '${acrLoginServer}/${imageName}'
          command: [
            'python'
            '-m'
            'backend.worker'
          ]
          env: [
            { name: 'AZURE_STORAGE_ENDPOINT', value: storageEndpoint }
            { name: 'AZURE_COSMOS_ENDPOINT', value: cosmosEndpoint }
            { name: 'AZURE_COSMOS_DATABASE_NAME', value: cosmosDatabaseName }
            { name: 'AZURE_SERVICE_BUS_NAMESPACE', value: '${serviceBusNamespaceName}.servicebus.windows.net' }
            { name: 'AZURE_SERVICE_BUS_QUEUE_NAME', value: claimsIngestionQueueName }
            { name: 'AZURE_SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'AZURE_KEY_VAULT_ENDPOINT', value: keyVaultEndpoint }
            { name: 'AZURE_DOC_INTELLIGENCE_ENDPOINT', value: docIntelligenceEndpoint }
            { name: 'AZURE_DOC_INTELLIGENCE_MODEL_ID', value: docIntelligenceModelId }
            { name: 'AZURE_SPEECH_ENDPOINT', value: speechEndpoint }
            { name: 'AZURE_TRANSLATOR_ENDPOINT', value: translatorEndpoint }
            { name: 'AZURE_TRANSLATOR_REGION', value: translatorRegion }
            { name: 'AZURE_CONTENT_UNDERSTANDING_ENDPOINT', value: contentUnderstandingEndpoint }
            { name: 'AZURE_FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'FOUNDRY_MODEL_DEPLOYMENT', value: modelDeploymentName }
            { name: 'CLAIMPILOT_USE_STUBS', value: claimpilotUseStubs ? '1' : '0' }
            { name: 'WORKER_MODE', value: '1' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
}

output workerAppName string = workerApp.name
output workerAppPrincipalId string = workerApp.identity.principalId
