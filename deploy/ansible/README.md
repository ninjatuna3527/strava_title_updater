# Ansible deploy

This folder contains an example Ansible playbook to deploy the application to a VPS.

Quick usage (local run):

1. Copy `inventory.ini.example` to `inventory.ini` and update host/user/port.
2. Copy `vars.yml.example` to `vars.yml` and update `deploy_path` and `supervisor_program`.
3. Run:

```bash
ansible-playbook -i inventory.ini playbook.yml --extra-vars "deploy_path=/srv/strava_title_updater supervisor_program=strava"
```

The playbook will:
- install required APT packages (`git`, `python3-venv`, `python3-pip`, `supervisor`)
- clone or update the repo into `deploy_path`
- create a virtualenv and install `requirements.txt`
- render a Supervisor program file to `/etc/supervisor/conf.d/` and restart the program

The GitHub Actions workflow has been updated to run this playbook from CI when deploying to the VPS.

The nginx role uses `ngx_http_limit_req_module` to rate-limit all application
routes per client IP. The default permits an average of 10 requests per second
with a burst of 20 and returns HTTP 429 when the limit is exceeded. Override
`nginx_rate_limit_rate`, `nginx_rate_limit_burst`,
`nginx_rate_limit_zone_size`, or `nginx_rate_limit_status` as needed. ACME
challenge requests are left unrestricted for certificate renewal.

The nginx template also disables version tokens, restricts TLS to versions
1.2 and 1.3, blocks dotfiles and common `/admin` probes, and adds CSP, HSTS,
frame, MIME-sniffing, referrer, and permissions headers. `/admin` remains
denied unless trusted networks are added to `nginx_admin_allowed_cidrs`. The
default CSP permits the app's existing inline CSS and Google Fonts while
restricting scripts to same-origin assets.

Production also enables ModSecurity v3 for nginx with the packaged OWASP Core
Rule Set. It runs in blocking mode at paranoia level 1 with the CRS default
inbound/outbound anomaly thresholds of 5 and 4. Set `nginx_waf_mode` to
`DetectionOnly` for tuning, or adjust `nginx_waf_paranoia_level` and the
anomaly threshold variables after reviewing
`/var/log/nginx/modsecurity_audit.log`. ACME validation and the health endpoint
are excluded from WAF inspection.

Production installs `msmtp-mta` to provide a sendmail-compatible SMTP relay.
Set the `SMTP_SENDER`, `SMTP_USER`, and `ADMIN_EMAIL` GitHub environment
variables and the `SMTP_PASS` environment secret. `SMTP_USER` is the relay
login and may differ from the sender address. `SMTP_HOST` and `SMTP_PORT`
select the relay and must be configured explicitly. `SMTP_SECURITY` accepts
`starttls`, `ssl`, or `unencrypted` and defaults to `starttls`. Local mail for
`root` and the deployment user is forwarded to `ADMIN_EMAIL`.
