param location string
param projectName string
param environment string
param tags object = {}

var logAnalyticsName = '${projectName}-${environment}-logs'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
  tags: tags
}

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${projectName}-${environment}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
  tags: tags
}

output environmentName string = containerAppsEnv.name
output environmentId string = containerAppsEnv.id
output logAnalyticsWorkspaceId string = logAnalytics.id
