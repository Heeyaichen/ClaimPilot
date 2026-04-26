param location string
param projectName string
param environment string
param tags object = {}

var accountName = '${projectName}-${environment}-cosmos'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    enableFreeTier: false
    enableAutomaticFailover: false
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
      maxIntervalInSeconds: 5
      maxStalenessPrefix: 100
    }
  }
  tags: tags
}

resource claimsDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: 'claimpilot-db'
  properties: {
    resource: {
      id: 'claimpilot-db'
    }
  }
}

resource claimsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: claimsDatabase
  name: 'claims'
  properties: {
    resource: {
      id: 'claims'
      partitionKey: {
        paths: [
          '/policyId'
        ]
        kind: 'Hash'
      }
    }
  }
}

resource policiesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: claimsDatabase
  name: 'policies'
  properties: {
    resource: {
      id: 'policies'
      partitionKey: {
        paths: [
          '/policyNumber'
        ]
        kind: 'Hash'
      }
    }
  }
}

resource auditLogContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: claimsDatabase
  name: 'audit_log'
  properties: {
    resource: {
      id: 'audit_log'
      partitionKey: {
        paths: [
          '/claimId'
        ]
        kind: 'Hash'
      }
    }
  }
}

output cosmosAccountName string = cosmosAccount.name
output cosmosAccountId string = cosmosAccount.id
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = claimsDatabase.name
