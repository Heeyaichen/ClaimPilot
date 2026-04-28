param location string
param projectName string
param environment string
param tags object = {}
param modelDeploymentName string = 'gpt-5-4'

var resourceName = '${projectName}-${environment}-foundry'
var projectName_val = '${projectName}-${environment}-project'

// Azure AI Foundry resource (Cognitive Services account kind: AIServices)
resource foundryResource 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: resourceName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
  tags: tags
}

// Foundry project
resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2024-10-01' = {
  parent: foundryResource
  name: projectName_val
  location: location
  properties: {}
  tags: tags
}

output foundryResourceName string = foundryResource.name
output foundryResourceId string = foundryResource.id
output foundryResourceEndpoint string = foundryResource.properties.endpoint
output foundryProjectName string = foundryProject.name
output foundryProjectId string = foundryProject.id
output foundryProjectEndpoint string = '${foundryResource.properties.endpoint}projects/${projectName_val}'
output modelDeploymentName string = modelDeploymentName
output foundryWorkspaceName string = foundryResource.name
