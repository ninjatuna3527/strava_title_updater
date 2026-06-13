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


def render_nginx_config(enable_tls, nginx_waf_enabled=True):
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        autoescape=False,
    )
    return environment.get_template("nginx.conf.j2").render(
        nginx_rate_limit_zone_size="10m",
        nginx_rate_limit_rate="2r/s",
        nginx_rate_limit_burst=20,
        nginx_rate_limit_status=429,
        nginx_admin_allowed_cidrs=["192.0.2.10/32"],
        nginx_ssl_ciphers="ECDHE-RSA-AES256-GCM-SHA384",
        nginx_content_security_policy=(
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"
        ),
        nginx_waf_enabled=nginx_waf_enabled,
        nginx_server_name="strava.example.com",
        base_path="/hanride",
        acme_webroot="/var/www/letsencrypt",
        enable_tls=enable_tls,
        ssl_cert_path="/tmp/fullchain.pem",
        ssl_key_path="/tmp/privkey.pem",
    )


def test_rate_limit_covers_all_http_application_locations():
    rendered = render_nginx_config(enable_tls=False)

    assert rendered.index("limit_req_zone ") < rendered.index("server {")
    assert rendered.count(
        "limit_req zone=hanride_per_ip burst=20 nodelay;"
    ) == 3
    assert rendered.count("limit_req_status 429;") == 1

    acme_location = rendered.split(
        "location ^~ /.well-known/acme-challenge/"
    )[1].split("}", 1)[0]
    assert "limit_req" not in acme_location


def test_rate_limit_covers_http_and_https_application_locations():
    rendered = render_nginx_config(enable_tls=True)

    assert rendered.count(
        "limit_req zone=hanride_per_ip burst=20 nodelay;"
    ) == 6
    assert rendered.count("limit_req_status 429;") == 2


def test_security_hardening_applies_to_both_server_blocks():
    rendered = render_nginx_config(enable_tls=True)

    assert "server_tokens off;" in rendered
    assert rendered.count("server_name strava.example.com;") == 2
    assert rendered.count('add_header X-Frame-Options "SAMEORIGIN" always;') == 2
    assert rendered.count(
        'add_header X-Content-Type-Options "nosniff" always;'
    ) == 2
    assert rendered.count("location ~ /\\.(?!well-known/)") == 2
    assert rendered.count("allow 192.0.2.10/32;") == 2
    assert rendered.count("deny all;") == 4

    assert "ssl_protocols TLSv1.2 TLSv1.3;" in rendered
    assert "ssl_ciphers 'ECDHE-RSA-AES256-GCM-SHA384';" in rendered
    assert "ssl_session_cache shared:SSL:10m;" in rendered
    assert (
        'add_header Strict-Transport-Security "max-age=31536000" always;'
        in rendered
    )
    assert (
        "script-src 'self'; style-src 'self' 'unsafe-inline' "
        "https://fonts.googleapis.com"
    ) in rendered


def test_modsecurity_covers_application_servers_but_not_operational_routes():
    rendered = render_nginx_config(enable_tls=True)

    assert rendered.count("modsecurity on;") == 2
    assert rendered.count(
        "modsecurity_rules_file /etc/nginx/modsecurity-hanride.conf;"
    ) == 2
    assert rendered.count('modsecurity_transaction_id "$server_name-$request_id";') == 2
    assert rendered.count("modsecurity off;") == 3


def test_modsecurity_directives_are_omitted_when_disabled():
    rendered = render_nginx_config(enable_tls=True, nginx_waf_enabled=False)

    assert "modsecurity " not in rendered
