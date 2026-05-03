param functionPrincipalId string
param location string
param projectName string
param environment string
param tags object = {}

// Resource IDs passed from parent for role assignment scoping
param storageAccountId string
param keyVaultId string
param cosmosAccountId string
param serviceBusNamespaceId string
param searchServiceId string
param docIntelligenceId string
param speechServiceId string
param translatorId string
param contentUnderstandingId string

// Storage Blob Data Contributor
resource rbacStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, storageAccountId, 'ba92f5b4')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: '${take(projectName, 4)}${environment}st${take(uniqueString(resourceGroup().id), 10)}'
}

// Key Vault Secrets User
resource rbacKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, keyVaultId, '4633458b')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Built-in Data Contributor
resource rbacCosmosContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, cosmosAccountId, '5bd9cd88')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5bd9cd88-fe45-4216-938b-f97437e15450')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Service Bus Data Sender
resource rbacServiceBusSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, serviceBusNamespaceId, '69a216fc')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Service Bus Data Receiver
resource rbacServiceBusReceiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, serviceBusNamespaceId, '4f6d3b9b')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
resource rbacSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, searchServiceId, '8ebe5a00')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User — Document Intelligence
resource rbacDocIntelUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, docIntelligenceId, 'a97b65f3-di')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User — Speech
resource rbacSpeechUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, speechServiceId, 'a97b65f3-speech')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User — Translator
resource rbacTranslatorUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, translatorId, 'a97b65f3-trans')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User — Content Understanding
resource rbacContentUnderstandingUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionPrincipalId, contentUnderstandingId, 'a97b65f3-cu')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}
