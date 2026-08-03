@description('Location for all resources.')
param location string = resourceGroup().location

@description('Name of the backend web app.')
param backendAppName string = 'app-onmac-store-backend'

@description('Name of the frontend static site.')
param frontendAppName string = 'stapp-onmac-store'

@description('Name of the App Service plan.')
param appServicePlanName string = 'asp-onmac-store'

@description('Name of the Application Insights resource.')
param appInsightsName string = 'appi-onmac-store'

@description('Name of the Log Analytics workspace.')
param logAnalyticsName string = 'log-onmac-store'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    Flow_Type: 'BlueGreen'
    Request_Source: 'rest'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource backendApp 'Microsoft.Web/sites@2023-12-01' = {
  name: backendAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appSettings: [
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
      ]
    }
  }
}

resource frontendApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: frontendAppName
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    repositoryUrl: ''
    branch: 'main'
    buildProperties: {
      appLocation: '/'
      apiLocation: ''
      outputLocation: 'dist'
    }
  }
}

output backendAppUrl string = 'https://${backendApp.properties.defaultHostName}'
output frontendAppUrl string = frontendApp.properties.defaultHostname
