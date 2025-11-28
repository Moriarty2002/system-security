# XACML Policy Structure Diagram

## PolicySet: file-storage-policies

```
PolicySet: file-storage-policies
├── Combining Algorithm: deny-overrides
│
├── Policy 1: user-file-operations (Target: role="user")
│   ├── Rule: user-can-upload (Effect: Permit)
│   │   └── Action: upload
│   │
│   ├── Rule: user-can-list-own-files (Effect: Permit)
│   │   ├── Action: list
│   │   └── Condition: username == resource-owner
│   │
│   ├── Rule: user-can-download-own-files (Effect: Permit)
│   │   ├── Action: download
│   │   └── Condition: username == resource-owner
│   │
│   ├── Rule: user-can-delete-own-files (Effect: Permit)
│   │   ├── Action: delete
│   │   └── Condition: username == resource-owner
│   │
│   ├── Rule: user-can-create-directory (Effect: Permit)
│   │   └── Action: mkdir
│   │
│   └── Rule: user-can-manage-bin (Effect: Permit)
│       └── Action: bin
│
├── Policy 2: moderator-operations (Target: role="moderator")
│   ├── Rule: moderator-can-list-all-files (Effect: Permit)
│   │   └── Action: list
│   │
│   ├── Rule: moderator-can-download-all-files (Effect: Permit)
│   │   └── Action: download
│   │
│   ├── Rule: moderator-can-list-users (Effect: Permit)
│   │   └── Action: list-users
│   │
│   ├── Rule: moderator-cannot-upload (Effect: Deny)
│   │   └── Action: upload
│   │
│   └── Rule: moderator-cannot-mkdir (Effect: Deny)
│       └── Action: mkdir
│
└── Policy 3: admin-operations (Target: role="admin")
    ├── Rule: admin-can-list-users (Effect: Permit)
    │   └── Action: admin-list-users
    │
    ├── Rule: admin-can-update-quota (Effect: Permit)
    │   ├── Action: update-quota
    │   └── Condition: target-role NOT IN [admin, moderator]
    │
    ├── Rule: admin-can-cleanup-bin (Effect: Permit)
    │   └── Action: cleanup-bin
    │
    └── Rule: admin-cannot-access-files (Effect: Deny)
        └── Actions: upload, download, list, delete, mkdir, bin
```

## Evaluation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    1. Request Arrives                        │
│  Subject: {username: "alice", role: "user"}                 │
│  Action: "upload"                                            │
│  Resource: {resource-owner: "alice"}                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              2. PEP Constructs XACML Request                │
│  - Extract user from JWT token                              │
│  - Determine action from endpoint                           │
│  - Get resource attributes (owner, etc.)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              3. PDP Evaluates Request                       │
│  For each Policy in PolicySet:                              │
│    a. Check Policy Target (role match?)                     │
│    b. If match, evaluate Rules                              │
│    c. For each Rule:                                        │
│       - Check Rule Target (action match?)                   │
│       - Check Rule Condition (if present)                   │
│       - Return Effect (Permit/Deny)                         │
│    d. Apply deny-overrides (any Deny → Deny)               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         4. Apply PolicySet Combining Algorithm              │
│  deny-overrides:                                            │
│    - If any Policy returns Deny → Final: Deny               │
│    - If any Policy returns Permit and none Deny → Permit    │
│    - Otherwise → NotApplicable                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              5. PEP Enforces Decision                       │
│  If Permit:                                                 │
│    - Log decision                                           │
│    - Execute endpoint                                       │
│  If Deny:                                                   │
│    - Log denial                                             │
│    - Return 403 Forbidden                                   │
└─────────────────────────────────────────────────────────────┘
```

## Example Evaluations

### Example 1: User uploads file

```
Request:
  Subject: {username: "alice", role: "user"}
  Action: "upload"
  Resource: {}

Evaluation:
1. Check Policy 1 (user-file-operations)
   Target: role="user" ✓ MATCH
   
2. Evaluate Rules in Policy 1:
   - Rule: user-can-upload
     Target: action="upload" ✓ MATCH
     Condition: None
     Effect: Permit ✓
   
3. Policy 1 returns: Permit

4. PolicySet combining: Permit (no Deny)

Result: ✅ Permit
```

### Example 2: Moderator tries to upload

```
Request:
  Subject: {username: "bob", role: "moderator"}
  Action: "upload"
  Resource: {}

Evaluation:
1. Check Policy 1 (user-file-operations)
   Target: role="user" ✗ NO MATCH
   
2. Check Policy 2 (moderator-operations)
   Target: role="moderator" ✓ MATCH
   
3. Evaluate Rules in Policy 2:
   - Rule: moderator-cannot-upload
     Target: action="upload" ✓ MATCH
     Condition: None
     Effect: Deny ✓
   
4. Policy 2 returns: Deny

5. PolicySet combining: Deny (deny-overrides)

Result: ❌ Deny
```

### Example 3: User lists own files

```
Request:
  Subject: {username: "alice", role: "user"}
  Action: "list"
  Resource: {resource-owner: "alice"}

Evaluation:
1. Check Policy 1 (user-file-operations)
   Target: role="user" ✓ MATCH
   
2. Evaluate Rules in Policy 1:
   - Rule: user-can-list-own-files
     Target: action="list" ✓ MATCH
     Condition: username == resource-owner?
       "alice" == "alice" ✓ TRUE
     Effect: Permit ✓
   
3. Policy 1 returns: Permit

4. PolicySet combining: Permit (no Deny)

Result: ✅ Permit
```

### Example 4: User tries to list another user's files

```
Request:
  Subject: {username: "alice", role: "user"}
  Action: "list"
  Resource: {resource-owner: "bob"}

Evaluation:
1. Check Policy 1 (user-file-operations)
   Target: role="user" ✓ MATCH
   
2. Evaluate Rules in Policy 1:
   - Rule: user-can-list-own-files
     Target: action="list" ✓ MATCH
     Condition: username == resource-owner?
       "alice" == "bob" ✗ FALSE
     Effect: Not applicable
   
   - (No other rules match action="list")
   
3. Policy 1 returns: NotApplicable

4. Check Policy 2 (moderator-operations)
   Target: role="moderator" ✗ NO MATCH

5. Check Policy 3 (admin-operations)
   Target: role="admin" ✗ NO MATCH

6. PolicySet combining: NotApplicable → Deny (default deny)

Result: ❌ Deny (NotApplicable treated as Deny)
```

### Example 5: Moderator lists another user's files

```
Request:
  Subject: {username: "bob", role: "moderator"}
  Action: "list"
  Resource: {resource-owner: "alice"}

Evaluation:
1. Check Policy 1 (user-file-operations)
   Target: role="user" ✗ NO MATCH
   
2. Check Policy 2 (moderator-operations)
   Target: role="moderator" ✓ MATCH
   
3. Evaluate Rules in Policy 2:
   - Rule: moderator-can-list-all-files
     Target: action="list" ✓ MATCH
     Condition: None (no ownership check)
     Effect: Permit ✓
   
4. Policy 2 returns: Permit

5. PolicySet combining: Permit (no Deny)

Result: ✅ Permit
```

### Example 6: Admin tries to list files

```
Request:
  Subject: {username: "charlie", role: "admin"}
  Action: "list"
  Resource: {}

Evaluation:
1. Check Policy 1 (user-file-operations)
   Target: role="user" ✗ NO MATCH
   
2. Check Policy 2 (moderator-operations)
   Target: role="moderator" ✗ NO MATCH
   
3. Check Policy 3 (admin-operations)
   Target: role="admin" ✓ MATCH
   
4. Evaluate Rules in Policy 3:
   - Rule: admin-cannot-access-files
     Target: action IN [upload, download, list, delete, mkdir, bin]
       action="list" ✓ MATCH
     Condition: None
     Effect: Deny ✓
   
5. Policy 3 returns: Deny

6. PolicySet combining: Deny (deny-overrides)

Result: ❌ Deny
```

### Example 7: Admin updates user quota

```
Request:
  Subject: {username: "charlie", role: "admin"}
  Action: "update-quota"
  Resource: {target-role: "user"}

Evaluation:
1. Check Policy 3 (admin-operations)
   Target: role="admin" ✓ MATCH
   
2. Evaluate Rules in Policy 3:
   - Rule: admin-can-update-quota
     Target: action="update-quota" ✓ MATCH
     Condition: target-role NOT IN [admin, moderator]?
       "user" NOT IN ["admin", "moderator"] ✓ TRUE
     Effect: Permit ✓
   
3. Policy 3 returns: Permit

4. PolicySet combining: Permit (no Deny)

Result: ✅ Permit
```

### Example 8: Admin tries to update moderator quota

```
Request:
  Subject: {username: "charlie", role: "admin"}
  Action: "update-quota"
  Resource: {target-role: "moderator"}

Evaluation:
1. Check Policy 3 (admin-operations)
   Target: role="admin" ✓ MATCH
   
2. Evaluate Rules in Policy 3:
   - Rule: admin-can-update-quota
     Target: action="update-quota" ✓ MATCH
     Condition: target-role NOT IN [admin, moderator]?
       "moderator" NOT IN ["admin", "moderator"] ✗ FALSE
     Effect: Not applicable
   
   - (No other rules permit update-quota)
   
3. Policy 3 returns: NotApplicable

4. PolicySet combining: NotApplicable → Deny (default deny)

Result: ❌ Deny
```

## Combining Algorithms

### Deny-Overrides (Used in this implementation)

```
For each Policy/Rule:
  If Effect = Deny:
    Return Deny immediately (short-circuit)
    
If any Effect = Permit:
  Return Permit
  
Otherwise:
  Return NotApplicable
```

**Behavior:**
- ✅ Secure by default (any deny blocks access)
- ✅ Single deny rule can override multiple permit rules
- ✅ Suitable for security-critical applications

### Other Combining Algorithms (Not used, but available in XACML)

**Permit-Overrides:**
- Any Permit → final Permit
- All Deny → final Deny
- Less secure than deny-overrides

**First-Applicable:**
- First matching rule determines result
- Order-dependent

**Only-One-Applicable:**
- Error if more than one rule matches
- Ensures no policy conflicts

## Attribute Categories

### Subject Attributes (urn:oasis:names:tc:xacml:1.0:subject-category:access-subject)
- `username`: Authenticated user's username
- `role`: User's role (user, moderator, admin)

### Resource Attributes (urn:oasis:names:tc:xacml:3.0:attribute-category:resource)
- `resource-owner`: Owner of the resource
- `target-role`: Role of the target user (for admin operations)

### Action Attributes (urn:oasis:names:tc:xacml:3.0:attribute-category:action)
- `action`: Action being performed (upload, download, list, etc.)

### Environment Attributes (urn:oasis:names:tc:xacml:3.0:attribute-category:environment)
- Currently unused (can be extended for time-based policies)

---

This diagram shows the complete XACML policy structure and evaluation logic for the file storage application.
