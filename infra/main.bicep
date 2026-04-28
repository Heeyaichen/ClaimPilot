targetScope = 'subscription'

param location string = 'swedencentral'
param projectName string = 'claimpilot'
param environment string = 'dev'
param resourceGroupName string = '${projectName}-${environment}-rg'
param tags object = {
  project: projectName
  environment: environment
  managedBy: 'bicep'
}

// Compute hosting: 'functions' (intended) or 'containerapps' (live-validation fallback)
@allowed(['functions', 'containerapps'])
param backendHostKind string = 'functions'

// Image tag for Container Apps mode
param imageTag string = 'v1.0.0'

// ---------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// ---------------------------------------------------------------
// Data & AI Services (deployed regardless of host kind)
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

module foundry './modules/foundry.bicep' = {
  name: 'foundry-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
    modelDeploymentName: 'gpt-5-4'
  }
}

// ---------------------------------------------------------------
// Compute: Functions (intended architecture)
// ---------------------------------------------------------------

module functions './modules/functions.bicep' = if (backendHostKind == 'functions') {
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

// ---------------------------------------------------------------
// Compute: Container Apps (live-validation alternative)
// ---------------------------------------------------------------

module containerRegistry './modules/container-registry.bicep' = if (backendHostKind == 'containerapps') {
  name: 'container-registry-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module containerAppsEnv './modules/container-apps-environment.bicep' = if (backendHostKind == 'containerapps') {
  name: 'container-apps-env-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

module apiApp './modules/container-app-api.bicep' = if (backendHostKind == 'containerapps') {
  name: 'container-app-api-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
    environmentId: containerAppsEnv.outputs.environmentId
    acrLoginServer: containerRegistry.outputs.acrLoginServer
    acrName: containerRegistry.outputs.acrName
    imageName: 'claimpilot-backend:${imageTag}'
    storageEndpoint: storage.outputs.storageEndpoint
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    cosmosDatabaseName: cosmos.outputs.databaseName
    serviceBusNamespaceName: servicebus.outputs.serviceBusNamespaceName
    claimsIngestionQueueName: servicebus.outputs.claimsIngestionQueueName
    signalREndpoint: signalr.outputs.signalREndpoint
    searchEndpoint: search.outputs.searchServiceEndpoint
    keyVaultEndpoint: keyvault.outputs.keyVaultEndpoint
    docIntelligenceEndpoint: docIntelligence.outputs.docIntelligenceEndpoint
    speechEndpoint: speech.outputs.speechServiceEndpoint
    translatorEndpoint: translator.outputs.translatorEndpoint
    contentUnderstandingEndpoint: contentUnderstanding.outputs.contentUnderstandingEndpoint
    foundryProjectEndpoint: foundry.outputs.foundryProjectEndpoint
    modelDeploymentName: foundry.outputs.modelDeploymentName
    claimpilotUseStubs: true
  }
}

module workerApp './modules/container-app-worker.bicep' = if (backendHostKind == 'containerapps') {
  name: 'container-app-worker-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
    environmentId: containerAppsEnv.outputs.environmentId
    acrLoginServer: containerRegistry.outputs.acrLoginServer
    imageName: 'claimpilot-backend:${imageTag}'
    storageEndpoint: storage.outputs.storageEndpoint
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    cosmosDatabaseName: cosmos.outputs.databaseName
    serviceBusNamespaceName: servicebus.outputs.serviceBusNamespaceName
    claimsIngestionQueueName: servicebus.outputs.claimsIngestionQueueName
    signalREndpoint: signalr.outputs.signalREndpoint
    searchEndpoint: search.outputs.searchServiceEndpoint
    keyVaultEndpoint: keyvault.outputs.keyVaultEndpoint
    docIntelligenceEndpoint: docIntelligence.outputs.docIntelligenceEndpoint
    speechEndpoint: speech.outputs.speechServiceEndpoint
    translatorEndpoint: translator.outputs.translatorEndpoint
    contentUnderstandingEndpoint: contentUnderstanding.outputs.contentUnderstandingEndpoint
    foundryProjectEndpoint: foundry.outputs.foundryProjectEndpoint
    modelDeploymentName: foundry.outputs.modelDeploymentName
    claimpilotUseStubs: true
  }
}

module frontendApp './modules/container-app-frontend.bicep' = if (backendHostKind == 'containerapps') {
  name: 'container-app-frontend-deploy'
  scope: rg
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
    environmentId: containerAppsEnv.outputs.environmentId
    acrLoginServer: containerRegistry.outputs.acrLoginServer
    imageName: 'claimpilot-frontend:${imageTag}'
    apiBaseUrl: 'https://${apiApp.outputs.apiFqdn}'
  }
}

// ---------------------------------------------------------------
// RBAC — targets Function identity or Container App identities
// ---------------------------------------------------------------

module rbac './modules/rbac.bicep' = if (backendHostKind == 'functions') {
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

// RBAC for Container Apps — assigns roles to API and worker identities
module rbacContainerApps './modules/rbac-containerapps.bicep' = if (backendHostKind == 'containerapps') {
  name: 'rbac-containerapps-deploy'
  scope: rg
  params: {
    apiPrincipalId: apiApp!.outputs.apiAppPrincipalId
    workerPrincipalId: workerApp!.outputs.workerAppPrincipalId
    projectName: projectName
    environment: environment
    storageAccountId: storage.outputs.storageAccountId
    cosmosAccountId: cosmos.outputs.cosmosAccountId
    serviceBusNamespaceId: servicebus.outputs.serviceBusNamespaceId
    searchServiceId: search.outputs.searchServiceId
    docIntelligenceId: docIntelligence.outputs.docIntelligenceId
    speechServiceId: speech.outputs.speechServiceId
    translatorId: translator.outputs.translatorId
    contentUnderstandingId: contentUnderstanding.outputs.contentUnderstandingId
    foundryId: foundry.outputs.foundryResourceId
  }
}

// ---------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------

output resourceGroupName string = rg.name
output backendHostKind string = backendHostKind

// Data services
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

// Foundry
output foundryResourceName string = foundry.outputs.foundryResourceName
output foundryProjectName string = foundry.outputs.foundryProjectName
output foundryProjectEndpoint string = foundry.outputs.foundryProjectEndpoint
output modelDeploymentName string = foundry.outputs.modelDeploymentName

// Functions outputs (only when backendHostKind == 'functions')
output functionAppName string = backendHostKind == 'functions' ? functions.outputs.functionAppName : ''
output functionAppPrincipalId string = backendHostKind == 'functions' ? functions.outputs.functionAppPrincipalId : ''

// Container Apps outputs (only when backendHostKind == 'containerapps')
output apiFqdn string = backendHostKind == 'containerapps' ? apiApp!.outputs.apiFqdn : ''
output workerAppName string = backendHostKind == 'containerapps' ? workerApp!.outputs.workerAppName : ''
output frontendFqdn string = backendHostKind == 'containerapps' ? frontendApp!.outputs.frontendFqdn : ''
output acrLoginServer string = backendHostKind == 'containerapps' ? containerRegistry!.outputs.acrLoginServer : ''
