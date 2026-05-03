using '../main.bicep'

param projectName = 'claimpilot'
param environment = 'devse'
param location = 'swedencentral'
param resourceGroupName = 'claimpilot-devse-rg'
param tags = {
  project: 'claimpilot'
  environment: 'devse'
  managedBy: 'bicep'
  owner: 'platform-team'
  costCenter: 'engineering'
}
