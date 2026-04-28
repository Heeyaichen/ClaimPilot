using '../main.bicep'

param projectName = 'claimpilot'
param environment = 'devca'
param location = 'swedencentral'
param resourceGroupName = 'claimpilot-devca-rg'
param backendHostKind = 'containerapps'
param imageTag = 'v1.0.0'
param tags = {
  project: 'claimpilot'
  environment: 'devca'
  managedBy: 'bicep'
  owner: 'platform-team'
  costCenter: 'engineering'
}
