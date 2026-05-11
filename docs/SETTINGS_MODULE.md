# ManageAI Settings Module - Complete Implementation Guide

## Overview

The Settings module is a comprehensive, production-ready control panel for managing all aspects of your ManageAI platform. It provides admins and super admins with centralized control over features, users, authentication, APIs, storage, and system-wide audit logging.

---

## Architecture

### Backend Architecture (Django)

#### Models (in `apps/enterprise/models.py`)

1. **SystemModuleControl**
   - Controls enable/disable state of core modules (Tasks, Collaboration, Tickets, etc.)
   - Per-company configuration with audit trail
   - Real-time broadcast on changes

2. **UserAccessControl**
   - Fine-grained RBAC per user and module
   - Configurable actions: VIEW, CREATE, EDIT, DELETE, ADMIN, EXPORT
   - Optional expiry dates for temporary access
   - Validation of access rights with `is_valid` property

3. **AuthenticationSettings**
   - One-to-one relationship per company
   - Controls password policies, MFA requirements
   - Manages login methods (Email, Face Recognition, Both)
   - Session timeout and password expiry settings

4. **CloudStorageSettings**
   - Manages cloud storage provider configuration
   - Tracks storage usage and limits
   - Supports: AWS S3, Azure Blob, Google Cloud Storage, Local
   - Backup management and monitoring

5. **ServerFileAccess**
   - Audit log for admin file system access
   - Tracks path, access type, success/failure, IP address
   - Non-editable audit trail

6. **SystemSettingsAuditLog**
   - Comprehensive audit log for all settings changes
   - Stores old and new values for comparison
   - Entity-based tracking (which setting was changed)
   - Immutable for compliance

#### API Endpoints

```
# Module Control
POST   /api/settings/modules/
GET    /api/settings/modules/
PATCH  /api/settings/modules/{id}/

# User Access Control
POST   /api/settings/access-controls/
GET    /api/settings/access-controls/
PATCH  /api/settings/access-controls/{id}/
DELETE /api/settings/access-controls/{id}/

# Authentication Settings
GET    /api/settings/auth/
PATCH  /api/settings/auth/{id}/

# Cloud Storage Settings
GET    /api/settings/storage/
PATCH  /api/settings/storage/{id}/

# File Access Logs
GET    /api/settings/file-access/
POST   /api/settings/file-access/ (internal logging)

# Audit Logs
GET    /api/settings/audit-logs/

# Dashboard (comprehensive view)
GET    /api/settings/dashboard/
```

#### Permissions

- All settings endpoints require `IsAuthenticated` and `IsAdminLevel` permissions
- Super Admin and Admin roles only
- Company-scoped access via `CompanyScopedMixin`

#### Real-time Broadcasting

Settings changes are broadcast via Django Channels:
- Group: `settings_updates`
- Events: `settings.module_changed`, `settings.auth_changed`
- Enables real-time UI updates across all connected clients

---

### Frontend Architecture (React)

#### Components Structure

```
src/
├── pages/
│   └── Settings.jsx (main Settings page)
├── components/settings/
│   ├── ModuleControl.jsx
│   ├── UserAccessManagement.jsx
│   ├── AuthenticationSettings.jsx
│   ├── APIKeyManagement.jsx
│   ├── CloudStorageSettings.jsx
│   ├── ServerFileAccess.jsx
│   └── SettingsAuditLog.jsx
```

#### Settings.jsx (Main Page)

- Tab-based navigation for different sections
- Dashboard data fetching and state management
- Notification system for success/error feedback
- Auto-refresh capability for data consistency

#### Tab Components

##### 1. ModuleControl.jsx
- Toggle switches for each system module
- Visual feedback (enabled/disabled states)
- Last update timestamp
- One-click enabling/disabling

##### 2. UserAccessManagement.jsx
- Add new access controls with form validation
- Per-user, per-module action configuration
- Expiry date management
- Remove access controls
- Edit existing permissions

##### 3. AuthenticationSettings.jsx
- Password policy configuration
- Password expiry settings
- Minimum length requirements
- MFA toggle
- Session timeout control
- Face recognition toggle
- Save with change detection

##### 4. APIKeyManagement.jsx
- Add new API keys (with key masking)
- View key previews (truncated for security)
- Copy key preview to clipboard
- Track grants (who can use this key)
- Toggle active/inactive status
- Delete keys with confirmation

##### 5. CloudStorageSettings.jsx
- Provider selection (AWS S3, Azure, GCP, Local)
- Storage usage visualization (progress bar)
- Storage limit configuration
- Backup toggle
- Endpoint and bucket configuration
- Real-time usage percentage

##### 6. ServerFileAccess.jsx
- Hierarchical file browser
- Breadcrumb navigation
- Folder traversal
- Project structure overview
- Mock file system (can be connected to real API)

##### 7. SettingsAuditLog.jsx
- Timeline view of all settings changes
- Change type indicators (CREATE, UPDATE, DELETE, etc.)
- User who made the change
- Timestamp of change
- Before/after values
- Entity type identification

---

## Key Features

### 1. Module Control
- **Enable/Disable**: Toggle any system module on/off
- **Immediate Effect**: Changes take effect immediately
- **Audit Trail**: All changes logged with timestamp and user
- **Modules Available**:
  - Tasks
  - Collaboration
  - Tickets
  - Notifications
  - AI Chatbot
  - Monitoring
  - Connection Engine
  - Project Files
  - Analytics
  - Audit Logs

### 2. User Access Management
- **Fine-grained RBAC**: Control per-module, per-user access
- **Action-based**: VIEW, CREATE, EDIT, DELETE, ADMIN, EXPORT
- **Temporary Access**: Set expiry dates for temporary permissions
- **Validation**: `is_valid` property checks if access is currently valid
- **User Filtering**: Find and grant access to specific users

### 3. Authentication Control
- **Password Policies**: Enforce minimum length and expiry
- **Login Methods**: Email, Face Recognition, or Both
- **2FA Enforcement**: Require two-factor auth for all users
- **Session Timeout**: Control inactive session timeout
- **Forgot Password**: Toggle availability on login page

### 4. API Key Management
- **Secure Storage**: Keys hashed with SHA-256
- **Preview Display**: Only truncated key shown (e.g., "sk_...1234")
- **Provider Support**: OpenAI, Meta, Open Source, Other
- **Grant System**: Control which developers can access each key
- **Active/Inactive**: Toggle keys without deleting

### 5. Cloud Storage Management
- **Multi-Provider**: AWS S3, Azure Blob, GCP Storage, Local
- **Usage Monitoring**: Real-time storage usage tracking
- **Backup Control**: Enable/disable automatic backups
- **Storage Quotas**: Set and monitor storage limits
- **Configuration**: Endpoint URL and bucket management

### 6. Server File Access
- **Browser Interface**: Hierarchical file system browser
- **Read-only**: Safe inspection without modification
- **Breadcrumb Navigation**: Easy path tracking
- **Project Structure**: View Python, React, and other project files
- **Audit Logging**: All access logged with IP and timestamp

### 7. Comprehensive Audit Logging
- **Change Tracking**: Every setting change logged
- **Before/After**: Stores old and new values
- **User Attribution**: Track who made each change
- **Timestamp**: Precise timing of all changes
- **Immutable**: Cannot be edited or deleted
- **Entity Tracking**: Know exactly what entity was modified

---

## Usage Examples

### Enable/Disable a Module

```javascript
// Frontend
const handleModuleToggle = async (module) => {
  const response = await api.patch(
    `/api/settings/modules/${module.id}/`,
    { is_enabled: !module.is_enabled }
  );
  // UI updates automatically
};
```

### Grant User Access to Module

```javascript
// Frontend
const handleAddAccess = async () => {
  const response = await api.post("/api/settings/access-controls/", {
    user: userId,
    module: "TASKS",
    actions: ["VIEW", "CREATE", "EDIT"],
    expires_at: null // or set expiry date
  });
};
```

### Update Authentication Settings

```javascript
// Frontend
const handleSave = async () => {
  const response = await api.patch(
    `/api/settings/auth/${settings.id}/`,
    {
      allow_password_change: true,
      allow_forgot_password: true,
      password_expiry_days: 90,
      require_2fa: false,
      session_timeout_minutes: 60
    }
  );
};
```

### Add API Key

```javascript
// Frontend
const response = await api.post("/api/api-keys/", {
  name: "Production OpenAI",
  provider: "OPENAI",
  raw_key: "sk_...",
  notes: "For GPT-4 integration"
});
// Key is immediately hashed and stored securely
```

---

## Real-time Features

### WebSocket Broadcasting

Settings changes broadcast to all connected admins:

```python
# Backend - When module is toggled
async_to_sync(channel_layer.group_send)("settings_updates", {
    "type": "settings.module_changed",
    "module": instance.module,
    "is_enabled": instance.is_enabled,
})
```

### Frontend Connection

Connected to WebSocket group `settings_updates` for real-time updates.

---

## Database Queries

### Efficient Queries

```python
# Get all module controls for company with audit trail
modules = SystemModuleControl.objects.select_related(
    'company', 'changed_by'
).filter(company=company)

# Get user access controls with user details
access = UserAccessControl.objects.select_related(
    'user', 'granted_by'
).filter(company=company, is_enabled=True)

# Get recent audit logs with actor info
logs = SystemSettingsAuditLog.objects.select_related(
    'changed_by'
).filter(company=company).order_by('-created_at')[:20]
```

### Audit Trail Queries

```python
# Find all changes made by specific user
changes = SystemSettingsAuditLog.objects.filter(
    changed_by=user
).order_by('-created_at')

# Find all changes to specific entity
entity_changes = SystemSettingsAuditLog.objects.filter(
    entity_type='AUTH_SETTINGS',
    entity_id=auth_settings.id
).order_by('-created_at')
```

---

## Security Considerations

1. **Permission Checks**: All endpoints require IsAdminLevel permission
2. **Key Hashing**: API keys stored as SHA-256 hashes, never in plaintext
3. **Audit Trail**: All changes logged and immutable
4. **Company Scoping**: Data isolated per company
5. **Expiry Validation**: Access controls checked for validity
6. **IP Logging**: File access logged with IP address
7. **Change Tracking**: Before/after values stored for compliance

---

## Performance Optimizations

1. **Select Related**: Reduces N+1 queries for relationships
2. **Prefetch Related**: Optimizes many-to-many queries
3. **Indexed Queries**: Company and created_at fields indexed
4. **Pagination**: Ready for future pagination on audit logs
5. **Caching Ready**: Settings can be cached after initial fetch

---

## Migration Requirements

Run Django migrations to create tables:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## Testing Scenarios

### Module Toggle
1. Go to Settings > Module Control
2. Click toggle for any module
3. Verify UI updates immediately
4. Check audit log for the change

### User Access Grant
1. Go to Settings > User Access
2. Click "Add User Access"
3. Select user, module, and actions
4. Save and verify in list
5. Check audit log

### Authentication Update
1. Go to Settings > Authentication
2. Change password expiry or MFA setting
3. Click "Save Settings"
4. Verify change in database

### API Key Management
1. Go to Settings > API Keys
2. Add new key
3. Verify key preview (truncated)
4. Copy to clipboard
5. Delete with confirmation

### Storage Configuration
1. Go to Settings > Cloud Storage
2. Change provider or limit
3. Save and verify
4. Check usage progress bar

### Audit Trail Review
1. Go to Settings > Audit Logs
2. Review all changes chronologically
3. Click on change to see before/after
4. Filter by user or entity type

---

## Future Enhancements

1. **Webhook Configuration**: Allow settings changes to trigger webhooks
2. **Role Templates**: Pre-configured access templates
3. **Batch Operations**: Apply settings to multiple users
4. **Export Audit**: Export audit logs to CSV/PDF
5. **Change Scheduling**: Schedule settings changes for future
6. **Approval Workflow**: Multi-level approval for critical changes
7. **Integration Webhooks**: Notify external systems of changes
8. **Settings Diff**: Visual comparison of setting changes
9. **Rollback Capability**: Revert recent changes
10. **Custom Modules**: Allow dynamic module registration

---

## Support & Maintenance

- **Logging**: All operations logged in audit trail
- **Monitoring**: Real-time status indicators
- **Alerts**: Notifications on critical changes
- **Backup**: Storage backup settings management
- **Documentation**: Inline help and tooltips throughout UI

---

## Deployment Checklist

- [ ] Run Django migrations
- [ ] Verify IsAdminLevel permission class exists
- [ ] Test all Settings endpoints with Postman
- [ ] Verify WebSocket connections for real-time updates
- [ ] Test frontend Settings page in browser
- [ ] Verify audit logging works
- [ ] Check API key hashing
- [ ] Test role-based access restrictions
- [ ] Monitor performance with real data
- [ ] Backup database before first production deployment

---

## API Response Examples

### Get Dashboard Data
```json
{
  "modules": [
    {
      "id": 1,
      "module": "TASKS",
      "is_enabled": true,
      "changed_at": "2024-05-09T10:30:00Z",
      "changed_by_detail": { "email": "admin@example.com" }
    }
  ],
  "access_controls": [
    {
      "id": 1,
      "user_detail": { "email": "dev@example.com" },
      "module": "TASKS",
      "actions": ["VIEW", "CREATE"],
      "is_valid": true
    }
  ],
  "auth_settings": { ... },
  "storage_settings": { ... },
  "recent_audit_logs": [ ... ]
}
```

---

## Conclusion

The Settings module provides a comprehensive, secure, and user-friendly interface for managing all aspects of your ManageAI platform. With real-time updates, complete audit trails, and granular permission controls, it empowers admins to maintain full control while ensuring compliance and security.
