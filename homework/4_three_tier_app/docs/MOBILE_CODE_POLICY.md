# Mobile Code Security Policy

**NIST 800-53 SC-18 Compliance Documentation**  
**Version:** 1.0  
**Last Updated:** December 12, 2025  
**Compliance Level:** MODERATE

---

## 1. Purpose

This policy defines acceptable and unacceptable mobile code technologies for the Local Cloud application and establishes controls for authorization, monitoring, and secure use of mobile code within the system.

**Mobile Code Definition:** Any program, application, or content that can be transmitted across a network and executed on a remote system, including but not limited to JavaScript, HTML5, Java applets, and browser plugins.

---

## 2. Acceptable Mobile Code Technologies

The following mobile code technologies are **AUTHORIZED** for use in this system:

### ✅ JavaScript (ES6+)
- **Purpose:** Client-side authentication (Keycloak integration), UI interactions, token management
- **Source:** Self-hosted scripts in `/js/` directory and Keycloak server
- **Security Controls:** 
  - Content Security Policy (CSP) restricts execution to authorized sources
  - No `eval()` or dynamic code generation permitted
  - All scripts must be code-reviewed before deployment

### ✅ HTML5
- **Purpose:** Modern web application structure and features
- **Allowed Features:** 
  - Semantic HTML elements
  - LocalStorage (limited use for non-sensitive preferences)
  - Fetch API for HTTPS requests
  - Canvas (if needed for future features)
- **Prohibited Features:**
  - WebAssembly (not required for current functionality)
  - WebGL (not required for current functionality)
  - SharedArrayBuffer

### ✅ CSS3
- **Purpose:** Application styling and responsive design
- **Source:** Self-hosted and Pico CSS framework (with SRI)
- **Security Controls:** Subresource Integrity (SRI) for external stylesheets

---

## 3. Unacceptable Mobile Code Technologies

The following mobile code technologies are **PROHIBITED** in this system:

### ❌ Java Applets
- **Reason:** Known security vulnerabilities, deprecated by all major browsers
- **Action:** Immediate removal if detected

### ❌ Adobe Flash / Shockwave
- **Reason:** End-of-life, multiple critical vulnerabilities, no longer supported
- **Action:** Blocked at network and application level

### ❌ ActiveX Controls
- **Reason:** Windows-only, significant security risks, enables arbitrary code execution
- **Action:** Not applicable (not supported in modern browsers)

### ❌ VBScript
- **Reason:** Legacy technology with security vulnerabilities, limited browser support
- **Action:** Blocked by CSP policy

### ❌ Unauthorized Third-Party JavaScript Libraries
- **Reason:** Supply chain attacks, malicious code injection risk
- **Action:** Must be reviewed and approved before use

---

## 4. Authorization Requirements

### 4.1 Code Review Process
All mobile code must undergo security review before deployment:

1. **Developer Review:** Code author performs self-review
2. **Peer Review:** At least one other developer reviews code
3. **Security Check:** Verify compliance with this policy
4. **Approval:** Project lead approves for deployment

### 4.2 External Dependencies
External mobile code (libraries, frameworks) must:

- Be from trusted, reputable sources
- Include Subresource Integrity (SRI) hashes
- Be pinned to specific versions (no `@latest` tags)
- Have known security track record
- Be documented in `package.json` or this policy

**Current Approved External Dependencies:**
- **Pico CSS v2.0.6** - UI framework (https://picocss.com)
  - SRI: `sha384-+GeIG8KM2IHBaf9XYcoh89b9AJMPJLmhBg+pSI3XKKOvCVvqXJnMwMU8qFRQzFnS`
- **Keycloak JS Adapter** - Authentication (loaded from Keycloak server)
  - Source: Trusted internal Keycloak infrastructure

---

## 5. Monitoring and Control Mechanisms

### 5.1 Content Security Policy (CSP)
Enforces restrictions on mobile code execution:

```
Content-Security-Policy: 
  default-src 'self'; 
  script-src 'self' https://shared-keycloak-server:8443 'unsafe-inline'; 
  style-src 'self' https://unpkg.com 'unsafe-inline'; 
  img-src 'self' data:; 
  font-src 'self' data:; 
  connect-src 'self' https://shared-keycloak-server:8443; 
  frame-ancestors 'none'; 
  base-uri 'self'; 
  form-action 'self'
```

**CSP Violations:** Logged and reviewed weekly for security anomalies

### 5.2 HTTP Security Headers
Additional protection against mobile code attacks:

- `X-Content-Type-Options: nosniff` - Prevents MIME-sniffing attacks
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-XSS-Protection: 1; mode=block` - Browser XSS protection
- `Strict-Transport-Security` - Enforces HTTPS

### 5.3 Subresource Integrity (SRI)
All external resources include cryptographic hashes to verify integrity:
- Prevents tampering during transit
- Ensures code authenticity from trusted sources
- Browser validates hash before execution

### 5.4 Regular Security Audits
- **Frequency:** Quarterly
- **Scope:** Review all JavaScript code, dependencies, CSP violations
- **Tools:** Static analysis (ESLint with security plugins), dependency scanning
- **Documentation:** Audit findings logged and remediated

---

## 6. Development Guidelines

### 6.1 Secure Coding Practices
Developers must follow these guidelines:

1. **No Dynamic Code Execution**
   - Avoid `eval()`, `Function()`, `setTimeout(string)`, `setInterval(string)`
   - Use modern JavaScript patterns instead

2. **Input Validation**
   - Sanitize all user input before DOM manipulation
   - Use textContent instead of innerHTML where possible

3. **Token Management**
   - Tokens kept in memory only (Keycloak adapter)
   - No sensitive data in localStorage or sessionStorage

4. **Error Handling**
   - No sensitive information in client-side error messages
   - Log errors server-side only

### 6.2 Testing Requirements
- All JavaScript must have unit tests
- Security-focused test cases for authentication flows
- CSP policy validated in staging environment

---

## 7. Incident Response

### 7.1 Suspected Malicious Mobile Code
If malicious or unauthorized mobile code is detected:

1. **Immediate Action:** Disable affected functionality
2. **Investigation:** Identify source and scope of compromise
3. **Remediation:** Remove malicious code, patch vulnerability
4. **Review:** Update this policy if needed

### 7.2 CSP Violations
- All CSP violations logged to `/logs/csp-violations.log`
- Reviewed weekly for anomalies
- Repeated violations trigger security investigation

---

## 8. Policy Maintenance

### Review Schedule
- **Quarterly Reviews:** Assess policy effectiveness and update as needed
- **After Security Incidents:** Immediate review and updates
- **Technology Changes:** Review when adopting new frameworks/libraries

### Policy Owner
- **Owner:** DevSecOps Team
- **Contact:** security@local-cloud.internal

### Version History
| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-12 | Initial policy for NIST 800-53 SC-18 compliance | DevSecOps |

---

## 9. Compliance Verification

### NIST 800-53 SC-18 Requirements Met:

✅ **SC-18.a** - Define acceptable and unacceptable mobile code and technologies  
✅ **SC-18.b** - Authorize, monitor, and control the use of mobile code  

### Evidence:
- Content Security Policy implemented (Apache configuration)
- Subresource Integrity for all external resources
- Security headers deployed (X-Content-Type-Options, X-Frame-Options)
- Code review process documented
- Monitoring mechanisms in place (CSP reporting)

---

## 10. References

- NIST 800-53 Rev 5: SC-18 Mobile Code
- OWASP Secure Coding Practices
- Mozilla Web Security Guidelines
- Content Security Policy Level 3 (W3C)

---

**Approval:**
- [ ] Project Lead
- [ ] Security Officer
- [ ] Compliance Manager

**Next Review Date:** March 12, 2026
