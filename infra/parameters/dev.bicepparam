using '../main.bicep'

param projectName = 'claimpilot'
param environment = 'dev'
param location = 'eastus2'
param resourceGroupName = 'claimpilot-dev-rg'
param tags = {
  project: 'claimpilot'
  environment: 'dev'
  managedBy: 'bicep'
  owner: 'platform-team'
  costCenter: 'engineering'
}
