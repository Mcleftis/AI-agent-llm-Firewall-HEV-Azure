terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# 1. Resource Group
resource "azurerm_resource_group" "rg" {
  name     = "rg-hev-ai-agent"
  location = "West Europe"
}

# 2. Azure Container Registry (Για τα Docker images)
resource "azurerm_container_registry" "acr" {
  name                = "acrhevaiagent"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true
}

# 3. Log Analytics Workspace (Απαραίτητο για το Container Environment)
resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-hev-agent"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# 4. Azure Container Apps Environment (Το Serverless Kubernetes)
resource "azurerm_container_app_environment" "env" {
  name                       = "env-hev-agent"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
}

# 5. Το Container App (Ο ίδιος ο AI Agent)
resource "azurerm_container_app" "app" {
  name                         = "ca-hev-agent"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  template {
    container {
      name   = "hev-agent"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" # Placeholder, θα αντικατασταθεί από το CI/CD
      cpu    = 0.5
      memory = "1.0Gi"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}