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


def render_modsecurity_config():
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        autoescape=False,
    )
    return environment.get_template("modsecurity.conf.j2").render(
        nginx_waf_mode="On",
        nginx_waf_paranoia_level=1,
        nginx_waf_inbound_anomaly_threshold=5,
        nginx_waf_outbound_anomaly_threshold=4,
        nginx_waf_audit_log="/var/log/nginx/modsecurity_audit.log",
    )


def test_modsecurity_loads_crs_in_the_required_order():
    rendered = render_modsecurity_config()

    setup = rendered.index("Include /etc/modsecurity/crs/crs-setup.conf")
    exclusions_before = rendered.index(
        "Include /etc/modsecurity/crs/REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf"
    )
    rules = rendered.index("Include /usr/share/modsecurity-crs/rules/*.conf")
    exclusions_after = rendered.index(
        "Include /etc/modsecurity/crs/RESPONSE-999-EXCLUSION-RULES-AFTER-CRS.conf"
    )

    assert setup < exclusions_before < rules < exclusions_after


def test_modsecurity_enables_blocking_and_anomaly_scoring():
    rendered = render_modsecurity_config()

    assert "SecRuleEngine On" in rendered
    assert "setvar:tx.paranoia_level=1" in rendered
    assert "setvar:tx.inbound_anomaly_score_threshold=5" in rendered
    assert "setvar:tx.outbound_anomaly_score_threshold=4" in rendered
    assert "SecAuditLog /var/log/nginx/modsecurity_audit.log" in rendered
