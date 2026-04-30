param apiPrincipalId string
param workerPrincipalId string
param projectName string
param environment string
param storageAccountId string
param cosmosAccountId string
param serviceBusNamespaceId string
param searchServiceId string
param docIntelligenceId string
param speechServiceId string
param translatorId string
param contentUnderstandingId string
param foundryId string

// Storage Blob Data Contributor — both API and worker
resource rbacStorageApi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(apiPrincipalId, storageAccountId, 'ba92f5b4')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource rbacStorageWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workerPrincipalId, storageAccountId, 'ba92f5b4')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Service Bus Data Sender — API enqueues
resource rbacSbSenderApi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(apiPrincipalId, serviceBusNamespaceId, '69a216fc')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Service Bus Data Receiver — worker dequeues
resource rbacSbReceiverWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workerPrincipalId, serviceBusNamespaceId, '4f6d3b9b')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0')
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor — worker indexes
resource rbacSearchWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workerPrincipalId, searchServiceId, '8ebe5a00')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User — both API and worker
resource rbacDocIntelApi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(apiPrincipalId, docIntelligenceId, 'a97b65f3-di')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource rbacSpeechWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workerPrincipalId, speechServiceId, 'a97b65f3-sp')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource rbacTranslatorWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workerPrincipalId, translatorId, 'a97b65f3-tr')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource rbacCuWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workerPrincipalId, contentUnderstandingId, 'a97b65f3-cu')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource rbacFoundryWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workerPrincipalId, foundryId, 'a97b65f3-fnd')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB data-plane role — worker (via SQL role assignment, done post-deploy)
