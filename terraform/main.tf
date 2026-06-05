data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = "${var.prefix}-rg"
  location = var.location
}

resource "azurerm_consumption_budget_resource_group" "finops_budget" {
  name              = "${var.prefix}-budget"
  resource_group_id = azurerm_resource_group.main.id
  amount            = 20
  time_grain        = "Monthly"

  time_period {
    start_date = "2026-06-01T00:00:00Z"
    end_date   = "2030-06-01T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 50.0
    operator       = "GreaterThanOrEqualTo"
    contact_emails = ["eleftherios.eleftheriadis@example.com"]
  }

  notification {
    enabled        = true
    threshold      = 80.0
    operator       = "GreaterThanOrEqualTo"
    contact_emails = ["eleftherios.eleftheriadis@example.com"]
  }
}

resource "azurerm_container_registry" "acr" {
  name                = "${var.prefix}registry123"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false
}

resource "azurerm_key_vault" "kv" {
  name                        = "${var.prefix}-keyvault"
  location                    = azurerm_resource_group.main.location
  resource_group_name         = azurerm_resource_group.main.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  enable_rbac_authorization   = true
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = "${var.prefix}-law"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
}

resource "azurerm_container_app_environment" "env" {
  name                       = "${var.prefix}-env"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
}

resource "azurerm_container_app" "gateway" {
  name                         = "${var.prefix}-gateway"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = 0
    max_replicas = 3

    container {
      name   = "api-gateway"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.25
      memory = "0.5Gi"
    }

    http_scale_rule {
      name                = "http-scale-rule"
      concurrent_requests = "50"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 443
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.gateway.identity[0].principal_id
}

resource "azurerm_user_assigned_identity" "github_actions" {
  name                = "${var.prefix}-gh-identity"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

resource "azurerm_federated_identity_credential" "github_actions" {
  name                = "${var.prefix}-github-federation"
  resource_group_name = azurerm_resource_group.main.name
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  parent_id           = azurerm_user_assigned_identity.github_actions.id
  subject             = "repo:TO_USERNAME_SOU/TO_REPO_SOU:ref:refs/heads/main"
}

resource "azurerm_role_assignment" "rg_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github_actions.principal_id
}
