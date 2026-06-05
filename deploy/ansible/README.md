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
