# XACML Integration Guide

## Overview

The three-tier file storage application has been converted to use **XACML (eXtensible Access Control Markup Language)** for fine-grained authorization. This document explains the XACML implementation, architecture, and policy structure.

## What is XACML?

XACML is an OASIS standard for defining and evaluating access control policies. It provides:

- **Policy-based authorization**: Separate authorization logic from application code
- **Fine-grained access control**: Define precise rules for who can access what
- **Centralized policy management**: All access policies in one location
- **Attribute-based decisions**: Authorization based on subject, resource, action, and environment attributes
- **Standard compliance**: Industry-standard XML format for policies

## Architecture

### Components

The XACML implementation consists of three main components:

```
┌─────────────────────────────────────────────────────────┐
│                    Flask Application                     │
├─────────────────────────────────────────────────────────┤
│  Endpoints (files.py, admin.py)                         │
│         ↓                                                │
│  PEP (Policy Enforcement Point) - xacml_pep.py          │
│         ↓                                                │
│  PDP (Policy Decision Point) - xacml_pdp.py             │
│         ↓                                                │
│  Policies (policies.xml)                                │
└─────────────────────────────────────────────────────────┘
```

#### 1. **Policy Administration Point (PAP)**
- Location: `homework/4_three_tier_app/xacml/policies.xml`
- Defines all access control policies in XACML XML format
- Contains three main policies:
  - User file operations
  - Moderator operations  
  - Admin operations

#### 2. **Policy Decision Point (PDP)**
- Location: `be_flask/src/xacml_pdp.py`
- Evaluates authorization requests against XACML policies
- Implements XACML 3.0 evaluation logic
- Uses **deny-overrides** combining algorithm
- Returns Permit/Deny/NotApplicable decisions

#### 3. **Policy Enforcement Point (PEP)**
- Location: `be_flask/src/xacml_pep.py`
- Intercepts Flask endpoint requests
- Constructs XACML requests from user context
- Enforces PDP decisions (abort on deny)
- Provides decorators for easy integration

## Policy Structure

### Policy Combining Algorithm: Deny-Overrides

The PolicySet uses **deny-overrides**:
- If any policy returns Deny, the final decision is Deny
- If at least one policy returns Permit and none return Deny, the final decision is Permit
- Otherwise, NotApplicable

### Policies Overview

#### Policy 1: User File Operations

**Target**: Users with role="user"

**Permitted Actions**:
- `upload`: Upload files to their own storage
- `list`: List their own files (condition: username == resource-owner)
- `download`: Download their own files (condition: username == resource-owner)
- `delete`: Delete their own files (condition: username == resource-owner)
- `mkdir`: Create directories
- `bin`: Manage their recycle bin (list, restore, permanently delete)

**Example Rule** (users can upload):
```xml
<Rule RuleId="user-can-upload" Effect="Permit">
    <Description>Users can upload files to their own storage</Description>
    <Target>
        <AnyOf>
            <AllOf>
                <Match MatchId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">upload</AttributeValue>
                    <AttributeDesignator AttributeId="action"
                                       Category="urn:oasis:names:tc:xacml:3.0:attribute-category:action"
                                       DataType="http://www.w3.org/2001/XMLSchema#string"
                                       MustBePresent="true"/>
                </Match>
            </AllOf>
        </AnyOf>
    </Target>
</Rule>
```

#### Policy 2: Moderator Operations

**Target**: Users with role="moderator"

**Permitted Actions**:
- `list`: List any user's files (no ownership condition)
- `download`: Download any user's files
- `list-users`: View list of all users

**Denied Actions**:
- `upload`: Moderators cannot upload files
- `mkdir`: Moderators cannot create directories

**Example Rule** (moderators can list all files):
```xml
<Rule RuleId="moderator-can-list-all-files" Effect="Permit">
    <Description>Moderators can list any user's files</Description>
    <Target>
        <AnyOf>
            <AllOf>
                <Match MatchId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">list</AttributeValue>
                    <AttributeDesignator AttributeId="action"
                                       Category="urn:oasis:names:tc:xacml:3.0:attribute-category:action"
                                       DataType="http://www.w3.org/2001/XMLSchema#string"
                                       MustBePresent="true"/>
                </Match>
            </AllOf>
        </AnyOf>
    </Target>
</Rule>
```

#### Policy 3: Admin Operations

**Target**: Users with role="admin"

**Permitted Actions**:
- `admin-list-users`: List all users with details
- `update-quota`: Update user quotas (condition: target user is not admin or moderator)
- `cleanup-bin`: Clean up expired bin items

**Denied Actions**:
- `upload`, `download`, `list`, `delete`, `mkdir`, `bin`: Admins cannot perform file operations

**Example Rule** (admins can update quotas with condition):
```xml
<Rule RuleId="admin-can-update-quota" Effect="Permit">
    <Description>Admins can update user quotas</Description>
    <Target>
        <AnyOf>
            <AllOf>
                <Match MatchId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">update-quota</AttributeValue>
                    <AttributeDesignator AttributeId="action"
                                       Category="urn:oasis:names:tc:xacml:3.0:attribute-category:action"
                                       DataType="http://www.w3.org/2001/XMLSchema#string"
                                       MustBePresent="true"/>
                </Match>
            </AllOf>
        </AnyOf>
    </Target>
    <Condition>
        <Apply FunctionId="urn:oasis:names:tc:xacml:1.0:function:not">
            <Apply FunctionId="urn:oasis:names:tc:xacml:1.0:function:or">
                <Apply FunctionId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeDesignator AttributeId="target-role"
                                       Category="urn:oasis:names:tc:xacml:3.0:attribute-category:resource"
                                       DataType="http://www.w3.org/2001/XMLSchema#string"
                                       MustBePresent="false"/>
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">admin</AttributeValue>
                </Apply>
                <Apply FunctionId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeDesignator AttributeId="target-role"
                                       Category="urn:oasis:names:tc:xacml:3.0:attribute-category:resource"
                                       DataType="http://www.w3.org/2001/XMLSchema#string"
                                       MustBePresent="false"/>
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">moderator</AttributeValue>
                </Apply>
            </Apply>
        </Apply>
    </Condition>
</Rule>
```

## Implementation Details

### Using XACML in Flask Endpoints

#### Method 1: Decorator (Recommended)

Use the `@enforce_xacml` decorator to protect endpoints:

```python
from ..xacml_pep import enforce_xacml

@files_bp.route('/upload', methods=['POST'])
@enforce_xacml('upload')
def upload_file():
    # Only executes if XACML permits
    username, user, role = authenticate_user()
    # ... upload logic
```

With resource owner parameter:

```python
@files_bp.route('/files', methods=['GET'])
@enforce_xacml('list')  # Automatically uses ?user= query param as resource-owner
def list_files():
    username, user, role = authenticate_user()
    target = request.args.get('user') or username
    # ... list files for target user
```

#### Method 2: Direct Check

For programmatic authorization checks:

```python
from ..xacml_pep import check_xacml_permission

if check_xacml_permission(username, role, 'delete', resource_owner=file_owner):
    delete_file()
else:
    return jsonify({'error': 'access denied'}), 403
```

#### Method 3: Require Permission

Abort on denial:

```python
from ..xacml_pep import require_xacml_permission

require_xacml_permission(
    username=current_username,
    role=role,
    action='update-quota',
    target_role=target_user_role
)
# Continues only if permitted, otherwise aborts with 403
```

### XACML Request Attributes

When constructing authorization requests, the PEP provides:

**Subject Attributes**:
- `username`: Authenticated user's username
- `role`: User's role (user, moderator, admin)

**Resource Attributes**:
- `resource-owner`: Owner of the resource being accessed (optional)
- `target-role`: Role of the target user for admin operations (optional)

**Action Attribute**:
- `action`: Action being performed (upload, download, list, delete, etc.)

**Environment Attributes**:
- Currently unused, but can be extended for time-based policies

### PDP Evaluation Flow

```
1. PDP receives XACMLRequest
2. For each Policy in PolicySet:
   a. Check if Policy Target matches request
   b. If target matches, evaluate all Rules in Policy
   c. For each Rule:
      - Check Rule Target
      - Check Rule Condition (if present)
      - If both match, return Rule Effect (Permit/Deny)
   d. Apply deny-overrides rule combining algorithm
3. Apply deny-overrides policy combining algorithm
4. Return final Decision (Permit/Deny/NotApplicable)
```

## Benefits of XACML Implementation

### 1. **Separation of Concerns**
- Authorization logic separated from business logic
- Policies defined in declarative XML format
- Easy to audit and modify policies without code changes

### 2. **Fine-Grained Control**
- Attribute-based conditions (e.g., "users can only access their own files")
- Complex rules (e.g., "admins can update quotas except for other admins")
- Resource-level authorization

### 3. **Centralized Policy Management**
- All policies in single `policies.xml` file
- Easy to review complete authorization model
- Version control for policy changes

### 4. **Standards Compliance**
- XACML 3.0 standard format
- Interoperable with enterprise IAM systems
- Well-documented specification

### 5. **Security**
- Default deny (deny-overrides algorithm)
- Explicit permission rules required
- Audit logging of all authorization decisions

## Migration from Role-Based to XACML

### Before (Role-Based Access Control)

```python
@files_bp.route('/upload', methods=['POST'])
def upload_file():
    username, user, role = authenticate_user()
    
    # Hard-coded role checks
    if role not in ['user']:
        abort(403, description='only users can upload files')
    
    # ... business logic
```

### After (XACML-Based Access Control)

```python
@files_bp.route('/upload', methods=['POST'])
@enforce_xacml('upload')
def upload_file():
    username, user, role = authenticate_user()
    
    # Authorization handled by XACML
    # ... business logic
```

### What Changed

1. **Removed hard-coded role checks** from endpoint functions
2. **Added `@enforce_xacml` decorators** to protected endpoints
3. **Moved authorization logic** to `policies.xml`
4. **Created PDP/PEP modules** to evaluate and enforce policies

## Testing XACML Policies

### Manual Testing

Test as different users:

```bash
# Login as regular user
curl -X POST http://localhost/api/login -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"password123"}'

# Try to upload (should succeed for users)
curl -X POST http://localhost/api/upload -H "Authorization: Bearer <token>" \
  -F "file=@test.txt"

# Login as moderator
curl -X POST http://localhost/api/login -H "Content-Type: application/json" \
  -d '{"username":"bob_moderator","password":"password456"}'

# Try to upload (should fail for moderators)
curl -X POST http://localhost/api/upload -H "Authorization: Bearer <token>" \
  -F "file=@test.txt"
# Expected: 403 Access denied by authorization policy
```

### Automated Testing

Create unit tests for XACML evaluation:

```python
from src.xacml_pdp import check_authorization

def test_user_can_upload():
    result = check_authorization(
        username='alice',
        role='user',
        action='upload'
    )
    assert result == True

def test_moderator_cannot_upload():
    result = check_authorization(
        username='bob',
        role='moderator',
        action='upload'
    )
    assert result == False

def test_moderator_can_view_any_files():
    result = check_authorization(
        username='bob',
        role='moderator',
        action='list',
        resource_owner='alice'
    )
    assert result == True
```

## Modifying Policies

### Adding a New Action

1. **Define the action** in your application
2. **Add rules** to `policies.xml`:

```xml
<Rule RuleId="user-can-share" Effect="Permit">
    <Description>Users can share their own files</Description>
    <Target>
        <AnyOf>
            <AllOf>
                <Match MatchId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">share</AttributeValue>
                    <AttributeDesignator AttributeId="action"
                                       Category="urn:oasis:names:tc:xacml:3.0:attribute-category:action"
                                       DataType="http://www.w3.org/2001/XMLSchema#string"
                                       MustBePresent="true"/>
                </Match>
            </AllOf>
        </AnyOf>
    </Target>
</Rule>
```

3. **Apply decorator** to endpoint:

```python
@files_bp.route('/files/<filename>/share', methods=['POST'])
@enforce_xacml('share')
def share_file(filename):
    # ... implementation
```

4. **Restart application** to reload policies

### Adding a New Role

1. **Create policy** for the new role in `policies.xml`:

```xml
<Policy PolicyId="auditor-operations"
        RuleCombiningAlgId="urn:oasis:names:tc:xacml:3.0:rule-combining-algorithm:deny-overrides"
        Version="1.0">
    
    <Description>Allow auditors to view but not modify</Description>
    
    <Target>
        <AnyOf>
            <AllOf>
                <Match MatchId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">auditor</AttributeValue>
                    <AttributeDesignator AttributeId="role"
                                       Category="urn:oasis:names:tc:xacml:1.0:subject-category:access-subject"
                                       DataType="http://www.w3.org/2001/XMLSchema#string"
                                       MustBePresent="true"/>
                </Match>
            </AllOf>
        </AnyOf>
    </Target>
    
    <Rule RuleId="auditor-can-list" Effect="Permit">
        <!-- ... -->
    </Rule>
</Policy>
```

2. **Add role to LDAP** directory
3. **Restart application** to reload policies

## Troubleshooting

### Policy Not Applied

**Check**:
1. Policy file syntax is valid XML
2. Namespace declarations are correct
3. Application has restarted to reload policies
4. PDP initialization logs show success

### Authorization Denied Unexpectedly

**Debug**:
1. Check application logs for XACML decision reasons
2. Verify request attributes (username, role, action, resource-owner)
3. Test policy in isolation
4. Review deny-overrides algorithm behavior

### Example Debug Logs

```
INFO - XACML decision for alice (user) performing 'upload': Permit
WARNING - XACML denied access: user=bob, role=moderator, action=upload, resource_owner=bob
INFO - Policy user-file-operations returned PERMIT
DEBUG - Rule user-can-upload matched
```

## Security Considerations

### 1. **Default Deny**
- All requests denied unless explicitly permitted
- Deny-overrides ensures any deny rule blocks access

### 2. **Policy File Protection**
- `policies.xml` should have restricted permissions
- Only administrators should modify policies
- Version control all policy changes

### 3. **Audit Logging**
- All authorization decisions logged
- Include user, role, action, and decision
- Monitor for policy violations

### 4. **Regular Review**
- Periodically audit policies for correctness
- Remove obsolete rules
- Ensure alignment with business requirements

## Future Enhancements

### 1. **Obligations and Advice**
- Add post-authorization actions
- Example: Log access to sensitive files

### 2. **Environment Attributes**
- Time-based policies (business hours only)
- Location-based policies (IP restrictions)

### 3. **Dynamic Policies**
- Load policies from database
- Hot-reload without restart

### 4. **Policy Testing Framework**
- Automated policy validation
- Regression testing for policy changes

## References

- [OASIS XACML 3.0 Specification](http://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html)
- XACML Policy Structure: `homework/4_three_tier_app/xacml/policies.xml`
- PDP Implementation: `be_flask/src/xacml_pdp.py`
- PEP Implementation: `be_flask/src/xacml_pep.py`

## Summary

The application now uses XACML for enterprise-grade authorization:

✅ **Centralized policies** - All access rules in `policies.xml`  
✅ **Fine-grained control** - Attribute-based conditions  
✅ **Standards-compliant** - XACML 3.0 format  
✅ **Separation of concerns** - Authorization logic decoupled from code  
✅ **Audit-ready** - All decisions logged  
✅ **Maintainable** - Easy to review and modify policies
