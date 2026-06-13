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

Production installs `msmtp-mta` to provide a sendmail-compatible SMTP relay.
Set the `SMTP_SENDER` and `ADMIN_EMAIL` GitHub environment variables and the
`SMTP_PASS` environment secret. `SMTP_HOST` and `SMTP_PORT` select the relay
and must be configured explicitly. `SMTP_SECURITY` accepts `starttls`, `ssl`,
or `unencrypted` and defaults to `starttls`. Local mail for `root` and the
deployment user is forwarded to `ADMIN_EMAIL`.
