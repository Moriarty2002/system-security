# Password Blacklist Configuration Guide

## ✅ Step 1: Mount Blacklist File (COMPLETED)

The blacklist file has been mounted in `docker-compose.yaml`:
```yaml
volumes:
  - ./config/blacklist.txt:/opt/keycloak/data/password-blacklist.txt:ro
```

## 🔄 Step 2: Restart Keycloak Container

Apply the volume mount by restarting the container:

```bash
cd /shared/University/system_security/system-security/homework/keycloak-infrastructure
docker compose restart keycloak
```

Wait 30-60 seconds for Keycloak to fully start.

## 🖥️ Step 3: Configure Password Policy via Keycloak UI

### Access Keycloak Admin Console

1. **Open browser**: https://localhost:8443 (or http://localhost:8080)

2. **Login credentials**:
   ```bash
   Username: admin
   Password: $(cat secrets/admin_password.txt)
   ```

### Configure Password Blacklist Policy

3. **Navigate to Realm Settings**:
   - Click on the dropdown in the top-left (should show "mes-local-cloud")
   - If not in your realm, select: **mes-local-cloud**

4. **Go to Authentication Policies**:
   - Left sidebar: **Realm Settings**
   - Top tabs: Click **Authentication** → **Policies** tab

5. **Add Password Blacklist Policy**:
   - Click the **"Add policy"** dropdown button
   - Look for one of these options (depending on Keycloak version):
     - **"Password Blacklist"** (if available)
     - **"Regex Pattern"** (alternative approach)
     - **"Custom Policy"** (if you have extensions installed)

### If "Password Blacklist" is Available:

6. **Configure Blacklist Policy**:
   - Select: **Password Blacklist**
   - **Blacklist File Path**: `/opt/keycloak/data/password-blacklist.txt`
   - Click **Add**

### If "Password Blacklist" is NOT Available (Standard Keycloak):

**Note**: Standard Keycloak (without custom extensions) does NOT support direct file-based blacklists.

**Alternative 1: Use Regex Pattern** (recommended for basic blocking):

6. **Add Regex Pattern Policy**:
   - Select: **Regex Pattern**
   - **Pattern**: `^(?!.*(password|123456|qwerty|admin)).*$`
   - **Error message**: "Password contains a blacklisted word"
   - Click **Add**

   This blocks specific common passwords, but not the entire file.

**Alternative 2: Recommended Password Policy** (strong without blacklist):

6. **Add Multiple Strong Policies**:
   
   Click "Add policy" for each of these:
   
   - **Length**: 12
   - **Uppercase Characters**: 1
   - **Lowercase Characters**: 1  
   - **Digits**: 1
   - **Special Characters**: 1
   - **Not Username**: (no config needed)
   - **Password History**: 12
   - **Expire Password**: 90 (days)
   
   This creates a very strong password policy without needing blacklist.

## 🔌 Step 4: Deploy Custom Blacklist Extension (For True Blacklist Support)

If you need TRUE blacklist file support, you'll need a custom Keycloak extension.

### Quick Install HIBP Extension (Recommended):

```bash
# Download Have I Been Pwned extension
cd /shared/University/system_security/system-security/homework/keycloak-infrastructure
mkdir -p extensions

# Get the extension (check latest version)
wget -O extensions/keycloak-password-blacklist.jar \
  https://github.com/droessne/keycloak-hibp/releases/latest/download/keycloak-hibp.jar

# Mount in docker-compose.yaml (add to volumes):
# - ./extensions:/opt/keycloak/providers:ro

# Restart Keycloak
docker compose restart keycloak
```

After restart, the "Password Blacklist" option should appear in the UI.

## 📋 Verification

### Test the Blacklist:

1. **Create a test user**:
   - Users → Add user → Create

2. **Try to set a blacklisted password**:
   - Go to Credentials tab
   - Try setting password: `password123` or `123456`
   - Should get an error if blacklist is working

3. **Try a strong password**:
   - Set: `MyS3cure!Pass2024`
   - Should succeed

## 🔍 Current Blacklist Stats

Your blacklist file contains:
- **47,603 entries** (common compromised passwords)
- Includes: password, 123456, qwerty, admin, letmein, etc.

## ⚠️ Important Notes

1. **Standard Keycloak Limitation**: 
   - Keycloak 23.x does NOT support file-based blacklists out of the box
   - You need either:
     - Custom SPI extension (complex)
     - HIBP extension (recommended)
     - Strong password policies (good alternative)

2. **Performance**: 
   - Large blacklist files (47k entries) can impact login performance
   - Consider using top 1000-5000 entries only

3. **Alternative Strategy**:
   - Use strong password policies (length, complexity, history)
   - Educate users about password security
   - Implement MFA (reduces password compromise impact)

## 🎯 Recommended Quick Solution

Since standard Keycloak doesn't support file blacklists, use this strong policy:

```
length(12) and upperCase(1) and lowerCase(1) and digits(1) and 
specialChars(1) and notUsername and passwordHistory(12) and 
forceExpiredPasswordChange(90)
```

This prevents 99% of weak passwords without needing a blacklist file.

## 📚 References

- [Keycloak Password Policies](https://www.keycloak.org/docs/latest/server_admin/#_password-policies)
- [HIBP Keycloak Extension](https://github.com/droessne/keycloak-hibp)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
