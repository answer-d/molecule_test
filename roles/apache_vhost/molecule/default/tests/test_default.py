import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_port_open(host):
    local = host.addr("localhost")

    assert local.port(8080).is_reachable


def test_httpd_enabled_n_started(host):
    httpd_svc = host.service("httpd")

    assert httpd_svc.is_running
    assert httpd_svc.is_enabled


def test_index(host):
    index = host.run("curl -LI http://localhost:8080 -s")

    assert index.rc == 0
    assert "200 OK" in index.stdout.split("\r\n")[0]
