# Sweet James Dashboard - Azure Web App Deployment Guide

## Prerequisites
- Azure subscription with Web App service
- Azure CLI installed locally
- Git repository with this code

## Azure Web App Configuration

### 1. Application Settings (Environment Variables)
Configure these in Azure Portal > App Service > Configuration > Application Settings:

#### Required Environment Variables:
```
ENVIRONMENT=production
SECRET_KEY=your-secure-secret-key-here
PORT=8000  # Azure will override this automatically

# Google Ads API
GOOGLE_ADS_DEVELOPER_TOKEN=your-token
GOOGLE_ADS_CLIENT_ID=your-client-id
GOOGLE_ADS_CLIENT_SECRET=your-client-secret
GOOGLE_ADS_REFRESH_TOKEN=your-refresh-token
GOOGLE_ADS_CUSTOMER_IDS=2419159990,8734393866,2065821782  # comma-separated
GOOGLE_ADS_MCC_ID=your-mcc-id  # if using MCC

# Salesforce/Litify API
LITIFY_USERNAME=your-username
LITIFY_PASSWORD=your-password
LITIFY_SECURITY_TOKEN=your-security-token

# For EntraID SSO (when implemented)
AZURE_CLIENT_ID=your-app-registration-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
```

### 2. Startup Command
In Azure Portal > App Service > Configuration > General Settings:
- **Startup Command**: `./startup.sh`

Or alternatively:
- **Startup Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:app`

### 3. Python Version
- **Python Version**: 3.9 or higher

## Deployment Steps

### Option 1: GitHub Actions (Recommended)
1. Connect your GitHub repository to Azure Web App
2. Azure will automatically create a GitHub Actions workflow
3. Push code to trigger deployment

### Option 2: Git Deployment
```bash
# Add Azure remote
git remote add azure https://<app-name>.scm.azurewebsites.net:443/<app-name>.git

# Deploy
git push azure main
```

### Option 3: ZIP Deployment
```bash
# Create deployment package
zip -r deploy.zip . -x "*.git*" "__pycache__*" "*.pyc"

# Deploy using Azure CLI
az webapp deployment source config-zip \
  --resource-group <resource-group> \
  --name <app-name> \
  --src deploy.zip
```

## Post-Deployment Setup

### 1. Verify Deployment
Visit: `https://<your-app-name>.azurewebsites.net/api/status`

### 2. Test Endpoints
- Dashboard: `https://<your-app-name>.azurewebsites.net/`
- Campaign Mapping: `https://<your-app-name>.azurewebsites.net/campaign-mapping`
- Forecasting: `https://<your-app-name>.azurewebsites.net/forecasting`

## EntraID SSO Integration (Next Steps)

### 1. App Registration
1. Go to Azure Portal > Azure Active Directory > App registrations
2. Create new registration for Sweet James Dashboard
3. Configure redirect URIs
4. Generate client secret

### 2. Code Integration
Add these packages to requirements.txt:
```
msal==1.24.0
flask-login==0.6.3
```

### 3. Authentication Flow
The app will need modifications to:
- Add login/logout routes
- Implement session management
- Protect routes with authentication decorators
- Integrate with Azure AD

## Monitoring & Logging

### Application Insights
1. Enable Application Insights in Azure Portal
2. Add instrumentation key to app settings
3. Install opencensus-ext-azure package

### Log Stream
Monitor real-time logs in Azure Portal > App Service > Log stream

## Troubleshooting

### Common Issues:
1. **Dependencies**: Ensure all packages in requirements.txt are compatible
2. **Environment Variables**: Double-check all API credentials
3. **Startup Command**: Verify startup.sh has execute permissions
4. **Port Binding**: Let Azure handle PORT environment variable

### Debug Mode:
For troubleshooting, temporarily set:
```
ENVIRONMENT=development
```
This will enable Flask's debug mode (not recommended for production).

## Security Considerations

1. **Never commit secrets** to repository
2. **Use Azure Key Vault** for sensitive credentials
3. **Enable HTTPS only** in Azure Web App settings
4. **Configure CORS** appropriately for your domain
5. **Implement rate limiting** for API endpoints

## Scaling

The app is configured with:
- 4 Gunicorn workers (can be adjusted in startup.sh)
- 120-second timeout for long-running requests
- Stateless design for horizontal scaling

Monitor performance and adjust worker count based on load.
