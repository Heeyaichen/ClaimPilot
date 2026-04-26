targetScope = 'subscription'

param location string = 'eastus2'
param projectName string = 'claimpilot'
param environment string = 'dev'
param resourceGroupName string = '${projectName}-${environment}-rg'
param tags object = {
  project: projectName
  environment: environment
  managedBy: 'bicep'
}

// ---------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// ---------------------------------------------------------------
// Module deployments (all scoped into the resource group)
// ---------------------------------------------------------------

module storage './modules/storage.bicep' = {
  name: 'storage-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module docIntelligence './modules/doc-intelligence.bicep' = {
  name: 'doc-intelligence-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module speech './modules/speech.bicep' = {
  name: 'speech-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module translator './modules/translator.bicep' = {
  name: 'translator-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module contentUnderstanding './modules/content-understanding.bicep' = {
  name: 'content-understanding-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module keyvault './modules/keyvault.bicep' = {
  name: 'keyvault-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module cosmos './modules/cosmos.bicep' = {
  name: 'cosmos-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module servicebus './modules/servicebus.bicep' = {
  name: 'servicebus-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module signalr './modules/signalr.bicep' = {
  name: 'signalr-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

// Search module skipped — eastus2 capacity exhausted. Uncomment when capacity available.
// module search './modules/search.bicep' = {
//   name: 'search-deploy'
//   scope: rg
//   params: {
//     location: location
//     projectName: projectName
//     environment: environment
//     tags: tags
//   }
// }

// Functions module skipped — subscription has 0 quota for App Service plans.
// Uncomment after requesting quota: https://portal.azure.com/#create/Microsoft.Support/Parameters/%7B%22subId%22%3A%226f6d44e3-1102-48ee-b4f9-3207cf1c63b6%22%2C%22pesId%22%3A%2276cbf240-4def-4a3e-b7e8-3a7e54c4a9b7%22%2C%22supportTopicId%22%3A%22e6e4ef12-5e5e-4c77-b8c8-7e2308ee6529%22%7D
// module functions './modules/functions.bicep' = {
//   name: 'functions-deploy'
//   scope: rg
//   params: {
//     location: location
//     projectName: projectName
//     environment: environment
//     tags: tags
//     storageAccountName: storage.outputs.storageAccountName
//     storageAccountEndpoint: storage.outputs.storageEndpoint
//   }
// }

module foundry './modules/foundry.bicep' = {
  name: 'foundry-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

// RBAC module skipped — depends on Functions (no quota).
// Uncomment along with Functions after quota is approved.
// module rbac './modules/rbac.bicep' = {
//   name: 'rbac-deploy'
//   scope: rg
//   params: {
//     functionPrincipalId: functions.outputs.functionAppPrincipalId
//     location: location
//     projectName: projectName
//     environment: environment
//     tags: tags
//     storageAccountId: storage.outputs.storageAccountId
//     keyVaultId: keyvault.outputs.keyVaultId
//     cosmosAccountId: cosmos.outputs.cosmosAccountId
//     serviceBusNamespaceId: servicebus.outputs.serviceBusNamespaceId
//     searchServiceId: search.outputs.searchServiceId
//     docIntelligenceId: docIntelligence.outputs.docIntelligenceId
//     speechServiceId: speech.outputs.speechServiceId
//     translatorId: translator.outputs.translatorId
//     contentUnderstandingId: contentUnderstanding.outputs.contentUnderstandingId
//   }
// }

// ---------------------------------------------------------------
// Outputs — all endpoint URLs and resource names
// ---------------------------------------------------------------

output resourceGroupName string = rg.name

output storageAccountName string = storage.outputs.storageAccountName
output storageEndpoint string = storage.outputs.storageEndpoint

output docIntelligenceEndpoint string = docIntelligence.outputs.docIntelligenceEndpoint
output docIntelligenceName string = docIntelligence.outputs.docIntelligenceName

output speechServiceEndpoint string = speech.outputs.speechServiceEndpoint
output speechServiceName string = speech.outputs.speechServiceName

output translatorEndpoint string = translator.outputs.translatorEndpoint
output translatorName string = translator.outputs.translatorName

output contentUnderstandingEndpoint string = contentUnderstanding.outputs.contentUnderstandingEndpoint
output contentUnderstandingName string = contentUnderstanding.outputs.contentUnderstandingName

output keyVaultName string = keyvault.outputs.keyVaultName
output keyVaultEndpoint string = keyvault.outputs.keyVaultEndpoint

output cosmosAccountName string = cosmos.outputs.cosmosAccountName
output cosmosEndpoint string = cosmos.outputs.cosmosEndpoint
output cosmosDatabaseName string = cosmos.outputs.databaseName

output serviceBusNamespaceName string = servicebus.outputs.serviceBusNamespaceName
output claimsIngestionQueueName string = servicebus.outputs.claimsIngestionQueueName

output signalRName string = signalr.outputs.signalRName
output signalREndpoint string = signalr.outputs.signalREndpoint

// Search outputs skipped — module commented out (region capacity)
// output searchServiceName string = search.outputs.searchServiceName
// output searchServiceEndpoint string = search.outputs.searchServiceEndpoint

// Function outputs skipped — module commented out (no subscription quota)
// output functionAppName string = functions.outputs.functionAppName
// output functionAppPrincipalId string = functions.outputs.functionAppPrincipalId
// output functionAppDefaultHostname string = functions.outputs.functionAppDefaultHostname

output foundryWorkspaceName string = foundry.outputs.foundryWorkspaceName
