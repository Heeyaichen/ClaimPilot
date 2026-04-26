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

module search './modules/search.bicep' = {
  name: 'search-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module functions './modules/functions.bicep' = {
  name: 'functions-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
    storageAccountName: storage.outputs.storageAccountName
    storageAccountEndpoint: storage.outputs.storageEndpoint
  }
}

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

// ---------------------------------------------------------------
// RBAC Role Assignments — delegated to RG-scoped module
// ---------------------------------------------------------------

module rbac './modules/rbac.bicep' = {
  name: 'rbac-deploy'
  scope: rg
  params: {
    functionPrincipalId: functions.outputs.functionAppPrincipalId
    location: location
    projectName: projectName
    environment: environment
    tags: tags
    storageAccountId: storage.outputs.storageAccountId
    keyVaultId: keyvault.outputs.keyVaultId
    cosmosAccountId: cosmos.outputs.cosmosAccountId
    serviceBusNamespaceId: servicebus.outputs.serviceBusNamespaceId
    searchServiceId: search.outputs.searchServiceId
    docIntelligenceId: docIntelligence.outputs.docIntelligenceId
    speechServiceId: speech.outputs.speechServiceId
    translatorId: translator.outputs.translatorId
    contentUnderstandingId: contentUnderstanding.outputs.contentUnderstandingId
  }
}

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

output searchServiceName string = search.outputs.searchServiceName
output searchServiceEndpoint string = search.outputs.searchServiceEndpoint

output functionAppName string = functions.outputs.functionAppName
output functionAppPrincipalId string = functions.outputs.functionAppPrincipalId
output functionAppDefaultHostname string = functions.outputs.functionAppDefaultHostname

output foundryWorkspaceName string = foundry.outputs.foundryWorkspaceName
