# LDAP Audit Logs

This directory contains audit logs from the OpenLDAP server.

## Log Files

- **slapd.log**: Main LDAP server logs including:
  - Connection attempts
  - Bind operations (authentication)
  - Search queries
  - Modify operations
  - Access control decisions

## Log Levels

The LDAP server is configured with log level 256 (stats) which includes:
- Connection events
- Operations performed
- Search filters used
- Results returned
- Timing information

## Security Monitoring

Monitor these logs for:
- ❌ Failed authentication attempts (INVALID_CREDENTIALS)
- 🔍 Unusual search patterns
- ⚠️ Excessive queries from single source
- 🚨 Unauthorized access attempts
- 🔐 TLS/SSL errors

## Log Rotation

Consider implementing log rotation for production:

```bash
# Add to cron or use logrotate
/path/to/ldap/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## Integration with SIEM

For production environments, forward these logs to a SIEM system:
- Splunk
- ELK Stack
- Graylog
- Azure Sentinel
