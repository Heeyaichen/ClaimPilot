param location string
param projectName string
param environment string
param tags object = {}

var keyVaultName = '${projectName}-${environment}-kv${take(uniqueString(resourceGroup().id), 6)}'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      name: 'standard'
      family: 'A'
    }
    enableSoftDelete: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 90
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

output keyVaultName string = keyVaultName
output keyVaultId string = keyVault.id
output keyVaultEndpoint string = keyVault.properties.vaultUri
