param location string
param projectName string
param environment string
param tags object = {}
param modelDeploymentName string = 'gpt-5-4'

var resourceName = '${projectName}-${environment}-foundry'
var projectName_val = '${projectName}-${environment}-project'

// Azure AI Foundry resource (Cognitive Services account kind: AIServices)
resource foundryResource 'Microsoft.CognitiveServices/accounts@2026-03-01' = {
  name: resourceName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    allowProjectManagement: true
    customSubDomainName: resourceName
  }
  tags: tags
}

// Foundry project — conditionally deployed.
// NOTE: The projects API in some regions (e.g. swedencentral) may return
// InternalServerError during ARM deployment. Set createProject=false to
// skip project creation; create it later via the Azure AI Foundry portal.
param createProject bool = true

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2026-03-01' = if (createProject) {
  parent: foundryResource
  name: projectName_val
  location: location
  properties: {}
  tags: tags
}

output foundryResourceName string = foundryResource.name
output foundryResourceId string = foundryResource.id
output foundryResourceEndpoint string = foundryResource.properties.endpoint
output foundryProjectName string = projectName_val
output foundryProjectId string = createProject ? foundryProject.id : '${foundryResource.id}/projects/${projectName_val}'
output foundryProjectEndpoint string = '${foundryResource.properties.endpoint}projects/${projectName_val}'
output modelDeploymentName string = modelDeploymentName
output foundryWorkspaceName string = foundryResource.name
