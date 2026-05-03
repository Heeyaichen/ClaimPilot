param location string
param projectName string
param environment string
param tags object = {}

var storageAccountName = '${take(projectName, 4)}${environment}st${take(uniqueString(resourceGroup().id), 10)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
  tags: tags
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource claimsIntake 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'claims-intake'
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountName string = storageAccountName
output storageAccountId string = storageAccount.id
output storageEndpoint string = storageAccount.properties.primaryEndpoints.blob
output claimsIntakeContainerName string = claimsIntake.name
