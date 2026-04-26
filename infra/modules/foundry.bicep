param location string
param projectName string
param environment string
param tags object = {}

// Stub module for Phase 2 Azure AI Foundry workspace.
// This module is intentionally empty and will be populated
// when Phase 2 implementation begins.

output foundryWorkspaceName string = '${projectName}-${environment}-foundry'
output foundryWorkspaceId string = ''
output foundryWorkspaceEndpoint string = ''
