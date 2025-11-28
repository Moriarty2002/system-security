# XACML Quick Reference

## Access Control Matrix

| Role      | Upload | Download Own | Download Any | List Own | List Any | Delete Own | Create Dir | Manage Bin | List Users | Update Quotas | Cleanup Bin |
|-----------|--------|--------------|--------------|----------|----------|------------|------------|------------|------------|---------------|-------------|
| User      | ✅     | ✅           | ❌           | ✅       | ❌       | ✅         | ✅         | ✅         | ❌         | ❌            | ❌          |
| Moderator | ❌     | ❌           | ✅           | ❌       | ✅       | ❌         | ❌         | ❌         | ✅         | ❌            | ❌          |
| Admin     | ❌     | ❌           | ❌           | ❌       | ❌       | ❌         | ❌         | ❌         | ✅         | ✅*           | ✅          |

\* Cannot update quotas for admins or moderators

## XACML Actions

| Endpoint | HTTP Method | XACML Action | Description |
|----------|-------------|--------------|-------------|
| `/api/upload` | POST | `upload` | Upload a file |
| `/api/files` | GET | `list` | List files |
| `/api/files/<filename>` | GET | `download` | Download a file |
| `/api/files/<filename>` | DELETE | `delete` | Delete a file |
| `/api/mkdir` | POST | `mkdir` | Create directory |
| `/api/bin` | GET | `bin` | List bin items |
| `/api/bin/<id>/restore` | POST | `bin` | Restore from bin |
| `/api/bin/<id>` | DELETE | `bin` | Permanently delete |
| `/api/bin/cleanup` | POST | `cleanup-bin` | Cleanup expired items |
| `/api/users` (moderator) | GET | `list-users` | List all usernames |
| `/api/admin/users` | GET | `admin-list-users` | List users with details |
| `/api/admin/users/<username>/quota` | PUT | `update-quota` | Update user quota |

## Quick Test Commands

### Test as User (alice)
```bash
# Login
TOKEN=$(curl -s -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"password123"}' | jq -r '.access_token')

# Upload (should succeed)
curl -X POST http://localhost/api/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.txt"

# List own files (should succeed)
curl http://localhost/api/files \
  -H "Authorization: Bearer $TOKEN"

# Try to list another user's files (should fail)
curl http://localhost/api/files?user=bob \
  -H "Authorization: Bearer $TOKEN"
```

### Test as Moderator (bob_moderator)
```bash
# Login
TOKEN=$(curl -s -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bob_moderator","password":"password456"}' | jq -r '.access_token')

# Upload (should fail - moderators cannot upload)
curl -X POST http://localhost/api/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.txt"

# List another user's files (should succeed)
curl http://localhost/api/files?user=alice \
  -H "Authorization: Bearer $TOKEN"

# Download another user's file (should succeed)
curl http://localhost/api/files/test.txt?user=alice \
  -H "Authorization: Bearer $TOKEN"

# List all users (should succeed)
curl http://localhost/api/users \
  -H "Authorization: Bearer $TOKEN"
```

### Test as Admin (charlie_admin)
```bash
# Login
TOKEN=$(curl -s -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"charlie_admin","password":"password789"}' | jq -r '.access_token')

# List files (should fail - admins cannot access files)
curl http://localhost/api/files \
  -H "Authorization: Bearer $TOKEN"

# List all users with details (should succeed)
curl http://localhost/api/admin/users \
  -H "Authorization: Bearer $TOKEN"

# Update user quota (should succeed)
curl -X PUT http://localhost/api/admin/users/alice/quota \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"quota": 10485760}'

# Try to update moderator quota (should fail)
curl -X PUT http://localhost/api/admin/users/bob_moderator/quota \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"quota": 10485760}'

# Cleanup bin (should succeed)
curl -X POST http://localhost/api/bin/cleanup \
  -H "Authorization: Bearer $TOKEN"
```

## Policy Locations

| Component | Location |
|-----------|----------|
| XACML Policies | `homework/4_three_tier_app/xacml/policies.xml` |
| PDP (Policy Decision Point) | `be_flask/src/xacml_pdp.py` |
| PEP (Policy Enforcement Point) | `be_flask/src/xacml_pep.py` |
| Files Blueprint | `be_flask/src/blueprints/files.py` |
| Admin Blueprint | `be_flask/src/blueprints/admin.py` |

## Common Policy Patterns

### Allow action for specific role
```xml
<Rule RuleId="role-can-action" Effect="Permit">
    <Target>
        <AnyOf>
            <AllOf>
                <Match MatchId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">ACTION</AttributeValue>
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

### Allow only if user owns resource
```xml
<Condition>
    <Apply FunctionId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
        <AttributeDesignator AttributeId="username"
                           Category="urn:oasis:names:tc:xacml:1.0:subject-category:access-subject"
                           DataType="http://www.w3.org/2001/XMLSchema#string"
                           MustBePresent="true"/>
        <AttributeDesignator AttributeId="resource-owner"
                           Category="urn:oasis:names:tc:xacml:3.0:attribute-category:resource"
                           DataType="http://www.w3.org/2001/XMLSchema#string"
                           MustBePresent="true"/>
    </Apply>
</Condition>
```

### Deny specific action
```xml
<Rule RuleId="role-cannot-action" Effect="Deny">
    <Target>
        <AnyOf>
            <AllOf>
                <Match MatchId="urn:oasis:names:tc:xacml:1.0:function:string-equal">
                    <AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">ACTION</AttributeValue>
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

## Expected Test Results

### User alice
- ✅ Upload files
- ✅ List own files
- ✅ Download own files  
- ✅ Delete own files
- ✅ Create directories
- ✅ Manage bin
- ❌ List other users' files
- ❌ Access admin functions

### Moderator bob_moderator
- ❌ Upload files
- ❌ Create directories
- ✅ List any user's files
- ✅ Download any user's files
- ✅ View user list
- ❌ Delete files
- ❌ Access admin functions

### Admin charlie_admin
- ❌ Upload/download/list files
- ❌ Access file operations
- ✅ List all users with details
- ✅ Update user quotas (except admin/moderator)
- ✅ Cleanup expired bin items
- ❌ Update admin/moderator quotas

## Logs to Monitor

### Successful Authorization
```
INFO - XACML decision for alice (user) performing 'upload': Permit
DEBUG - XACML permitted access: user=alice, role=user, action=upload, resource_owner=alice
```

### Denied Authorization
```
WARNING - XACML denied access: user=bob_moderator, role=moderator, action=upload, resource_owner=bob_moderator
```

### Policy Evaluation
```
DEBUG - Policy user-file-operations returned PERMIT
DEBUG - Rule user-can-upload matched
INFO - Successfully loaded XACML policies from /path/to/policies.xml
```

## Troubleshooting

### "Access denied by authorization policy"
- Check user's role in LDAP
- Verify action name matches policy
- Review `policies.xml` for applicable rules
- Check application logs for decision details

### Policy Not Loading
- Verify `policies.xml` syntax
- Check file path in `xacml_pdp.py`
- Restart Flask application
- Look for PDP initialization errors in logs

### Condition Not Working
- Verify attribute names match exactly
- Check that attributes are provided in request
- Test without condition first
- Enable debug logging

## Additional Resources

- Full documentation: `XACML_INTEGRATION.md`
- XACML 3.0 Spec: http://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html
