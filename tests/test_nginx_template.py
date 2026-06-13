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


def render_nginx_config(enable_tls):
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
