# XACML Integration Verification Checklist

Use this checklist to verify the XACML integration is working correctly.

## ✅ File Structure

- [x] `xacml/policies.xml` exists and contains XACML 3.0 policies
- [x] `be_flask/src/xacml_pdp.py` exists (Policy Decision Point)
- [x] `be_flask/src/xacml_pep.py` exists (Policy Enforcement Point)
- [x] `be_flask/src/blueprints/files.py` updated with `@enforce_xacml` decorators
- [x] `be_flask/src/blueprints/admin.py` updated with `@enforce_xacml` decorators
- [x] `XACML_INTEGRATION.md` documentation created
- [x] `xacml/XACML_QUICK_REFERENCE.md` quick reference created
- [x] `xacml/POLICY_STRUCTURE.md` policy diagram created
- [x] `XACML_CONVERSION_SUMMARY.md` summary created

## 📝 Code Changes

### blueprints/files.py
- [ ] Imports `enforce_xacml` from `..xacml_pep`
- [ ] `upload_file()` has `@enforce_xacml('upload')` decorator
- [ ] `list_files()` has `@enforce_xacml('list')` decorator
- [ ] `list_users_for_moderator()` has `@enforce_xacml('list-users')` decorator
- [ ] `download_file()` has `@enforce_xacml('download')` decorator
- [ ] `delete_file()` has `@enforce_xacml('delete')` decorator
- [ ] `create_directory()` has `@enforce_xacml('mkdir')` decorator
- [ ] `list_bin()` has `@enforce_xacml('bin')` decorator
- [ ] `restore_from_bin_endpoint()` has `@enforce_xacml('bin')` decorator
- [ ] `permanently_delete_from_bin_endpoint()` has `@enforce_xacml('bin')` decorator
- [ ] `cleanup_bin()` has `@enforce_xacml('cleanup-bin')` decorator
- [ ] All hard-coded role checks removed

### blueprints/admin.py
- [ ] Imports `enforce_xacml` and `require_xacml_permission` from `..xacml_pep`
- [ ] `list_users()` has `@enforce_xacml('admin-list-users')` decorator
- [ ] `update_quota()` uses `require_xacml_permission()` with target-role
- [ ] All `require_admin()` calls removed

### auth.py
- [ ] `require_admin()` function removed or commented out

## 🔍 Functional Tests

### Test as User (alice)

```bash
TOKEN=$(curl -s -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"password123"}' | jq -r '.access_token')
```

- [ ] ✅ Can upload file: `curl -X POST http://localhost/api/upload -H "Authorization: Bearer $TOKEN" -F "file=@test.txt"`
- [ ] ✅ Can list own files: `curl http://localhost/api/files -H "Authorization: Bearer $TOKEN"`
- [ ] ✅ Can download own file: `curl http://localhost/api/files/test.txt -H "Authorization: Bearer $TOKEN"`
- [ ] ✅ Can delete own file: `curl -X DELETE http://localhost/api/files/test.txt -H "Authorization: Bearer $TOKEN"`
- [ ] ✅ Can create directory: `curl -X POST http://localhost/api/mkdir -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"path":"testdir"}'`
- [ ] ✅ Can list bin: `curl http://localhost/api/bin -H "Authorization: Bearer $TOKEN"`
- [ ] ❌ Cannot list other user's files: `curl http://localhost/api/files?user=bob -H "Authorization: Bearer $TOKEN"` (expect 403)
- [ ] ❌ Cannot list users: `curl http://localhost/api/users -H "Authorization: Bearer $TOKEN"` (expect 403)
- [ ] ❌ Cannot access admin endpoints: `curl http://localhost/api/admin/users -H "Authorization: Bearer $TOKEN"` (expect 403)

### Test as Moderator (bob_moderator)

```bash
TOKEN=$(curl -s -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bob_moderator","password":"password456"}' | jq -r '.access_token')
```

- [ ] ❌ Cannot upload file: `curl -X POST http://localhost/api/upload -H "Authorization: Bearer $TOKEN" -F "file=@test.txt"` (expect 403)
- [ ] ❌ Cannot create directory: `curl -X POST http://localhost/api/mkdir -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"path":"testdir"}'` (expect 403)
- [ ] ✅ Can list any user's files: `curl http://localhost/api/files?user=alice -H "Authorization: Bearer $TOKEN"`
- [ ] ✅ Can download any user's file: `curl http://localhost/api/files/test.txt?user=alice -H "Authorization: Bearer $TOKEN"`
- [ ] ✅ Can list users: `curl http://localhost/api/users -H "Authorization: Bearer $TOKEN"`
- [ ] ❌ Cannot delete files: `curl -X DELETE http://localhost/api/files/test.txt?user=alice -H "Authorization: Bearer $TOKEN"` (expect 403)
- [ ] ❌ Cannot access admin endpoints: `curl http://localhost/api/admin/users -H "Authorization: Bearer $TOKEN"` (expect 403)

### Test as Admin (charlie_admin)

```bash
TOKEN=$(curl -s -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"charlie_admin","password":"password789"}' | jq -r '.access_token')
```

- [ ] ❌ Cannot upload file: `curl -X POST http://localhost/api/upload -H "Authorization: Bearer $TOKEN" -F "file=@test.txt"` (expect 403)
- [ ] ❌ Cannot list files: `curl http://localhost/api/files -H "Authorization: Bearer $TOKEN"` (expect 403)
- [ ] ❌ Cannot download files: `curl http://localhost/api/files/test.txt -H "Authorization: Bearer $TOKEN"` (expect 403)
- [ ] ❌ Cannot delete files: `curl -X DELETE http://localhost/api/files/test.txt -H "Authorization: Bearer $TOKEN"` (expect 403)
- [ ] ❌ Cannot access bin: `curl http://localhost/api/bin -H "Authorization: Bearer $TOKEN"` (expect 403)
- [ ] ✅ Can list all users: `curl http://localhost/api/admin/users -H "Authorization: Bearer $TOKEN"`
- [ ] ✅ Can update user quota: `curl -X PUT http://localhost/api/admin/users/alice/quota -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"quota":10485760}'`
- [ ] ❌ Cannot update admin quota: `curl -X PUT http://localhost/api/admin/users/charlie_admin/quota -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"quota":10485760}'` (expect 403)
- [ ] ❌ Cannot update moderator quota: `curl -X PUT http://localhost/api/admin/users/bob_moderator/quota -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"quota":10485760}'` (expect 403)
- [ ] ✅ Can cleanup bin: `curl -X POST http://localhost/api/bin/cleanup -H "Authorization: Bearer $TOKEN"`

## 📊 Log Verification

Check application logs for XACML decision logging:

```bash
docker compose logs backend | grep XACML
```

Expected log entries:
- [ ] `Successfully loaded XACML policies from /path/to/policies.xml`
- [ ] `XACML decision for <username> (<role>) performing '<action>': Permit`
- [ ] `XACML denied access: user=<username>, role=<role>, action=<action>`
- [ ] `XACML permitted access: user=<username>, role=<role>, action=<action>`

## 🔧 Policy Validation

### Policy File
- [ ] `xacml/policies.xml` is valid XML
- [ ] All policies have unique PolicyId
- [ ] All rules have unique RuleId
- [ ] Namespace declarations are correct
- [ ] PolicyCombiningAlgId is "deny-overrides"
- [ ] RuleCombiningAlgId is "deny-overrides"

### Policy Coverage
- [ ] Policy exists for role="user"
- [ ] Policy exists for role="moderator"
- [ ] Policy exists for role="admin"
- [ ] All actions mapped: upload, list, download, delete, mkdir, bin, cleanup-bin, list-users, admin-list-users, update-quota

### Conditions
- [ ] Ownership conditions work (username == resource-owner)
- [ ] Target role conditions work (target-role NOT IN [admin, moderator])

## 🚀 Deployment Verification

### Startup
- [ ] Application starts without errors
- [ ] PDP loads policies successfully
- [ ] No XACML initialization errors in logs

### Runtime
- [ ] All endpoints respond correctly
- [ ] Authorization decisions are logged
- [ ] 403 errors include "Access denied by authorization policy" message
- [ ] Performance is acceptable (policies cached in memory)

## 📚 Documentation

- [ ] README.md updated with XACML references
- [ ] XACML_INTEGRATION.md is complete and accurate
- [ ] XACML_QUICK_REFERENCE.md has all actions and test commands
- [ ] POLICY_STRUCTURE.md shows policy hierarchy
- [ ] XACML_CONVERSION_SUMMARY.md summarizes changes

## 🔐 Security Validation

- [ ] Default deny behavior works (NotApplicable → Deny)
- [ ] Deny-overrides combining algorithm enforced
- [ ] Users cannot escalate privileges
- [ ] Role-based policies correctly enforce separation
- [ ] Ownership conditions prevent unauthorized access
- [ ] Admin restrictions prevent privileged user quota updates

## 🐛 Troubleshooting

If tests fail, check:
- [ ] Policy file path is correct in `xacml_pdp.py`
- [ ] Application restarted after policy changes
- [ ] JWT tokens are valid and not expired
- [ ] User roles are correctly set in LDAP
- [ ] Decorator syntax is correct (`@enforce_xacml('action')`)
- [ ] Action names match exactly between code and policies

## 📝 Notes

Document any issues or observations:

```
Issue: 
Resolution: 

Issue: 
Resolution: 
```

## ✅ Final Checklist

- [ ] All file structure items verified
- [ ] All code changes reviewed
- [ ] User functional tests passed
- [ ] Moderator functional tests passed
- [ ] Admin functional tests passed
- [ ] Logs show correct XACML decisions
- [ ] Policy file validated
- [ ] All actions covered by policies
- [ ] Documentation complete
- [ ] Security validation passed
- [ ] Application deployed successfully

---

**Date Verified:** __________

**Verified By:** __________

**Status:** 
- [ ] ✅ All tests passed
- [ ] ⚠️ Some tests failed (see notes)
- [ ] ❌ Major issues (see notes)
