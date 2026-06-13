from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


TEMPLATE_DIR = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "ansible"
    / "roles"
    / "strava"
    / "templates"
)


def template_environment():
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        autoescape=False,
    )


def test_msmtp_config_uses_authenticated_starttls():
    rendered = template_environment().get_template("msmtprc.j2").render(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_security="starttls",
        smtp_sender="sender@example.com",
    )

    assert "auth on" in rendered
    assert "tls on" in rendered
    assert "tls_starttls on" in rendered
    assert "host smtp.example.com" in rendered
    assert "port 587" in rendered
    assert "user sender@example.com" in rendered
    assert 'passwordeval "cat /etc/msmtp-password"' in rendered


def test_msmtp_config_uses_implicit_tls():
    rendered = template_environment().get_template("msmtprc.j2").render(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security="ssl",
        smtp_sender="sender@example.com",
    )

    assert "tls on" in rendered
    assert "tls_starttls off" in rendered
    assert "tls_trust_file /etc/ssl/certs/ca-certificates.crt" in rendered


def test_msmtp_config_can_use_unencrypted_smtp():
    rendered = template_environment().get_template("msmtprc.j2").render(
        smtp_host="smtp.internal",
        smtp_port=25,
        smtp_security="unencrypted",
        smtp_sender="sender@example.com",
    )

    assert "tls off" in rendered
    assert "tls_starttls" not in rendered
    assert "tls_trust_file" not in rendered


def test_sendmail_aliases_forward_to_admin():
    rendered = template_environment().get_template("aliases.j2").render(
        ansible_user="deploy",
        admin_email="admin@example.com",
    )

    assert "root: admin@example.com" in rendered
    assert "deploy: admin@example.com" in rendered
    assert "default: admin@example.com" in rendered
