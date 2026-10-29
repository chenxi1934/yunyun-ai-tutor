"""新增本项目Nginx虚拟主机；HTTP-01获取真实证书并每日检查续期，保留既有站点。"""
import argparse
import ipaddress
import shlex
import subprocess
import urllib.request

from app.config import PROJECT_ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target')
    parser.add_argument('--domain', required=True)
    args = parser.parse_args()
    if any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in args.domain):
        parser.error('域名不合法')
    ssh = ['ssh', '-S', str(PROJECT_ROOT / '.runtime/ssh_control'), '-o',
        'UserKnownHostsFile=' + str(PROJECT_ROOT / '.runtime/ssh_known_hosts'), args.target]
    def run(cmd, data=None):
        subprocess.run([*ssh, cmd], input=data, check=True)
    def write(path, text, mode=0o600):
        code = f'import os,sys; f=os.open({path!r},os.O_WRONLY|os.O_CREAT|os.O_TRUNC,{mode}); os.write(f,sys.stdin.buffer.read()); os.fchmod(f,{mode}); os.close(f)'
        run('python3 -c ' + shlex.quote(code), text.encode())
    root = '/opt/yunyun-tutor'
    run(f'mkdir -p {root}/tls {root}/acme/.well-known/acme-challenge')
    source = urllib.request.urlopen('https://raw.githubusercontent.com/diafygi/acme-tiny/master/acme_tiny.py', timeout=30).read().decode()
    try:
        ipaddress.ip_address(args.domain)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip:
        # acme-tiny MIT客户端的最小RFC8738适配：IP identifier及shortlived profile。
        source = source.replace('if san.startswith("DNS:"):', 'if san.startswith(("DNS:", "IP Address:")):').replace('domains.add(san[4:])', 'domains.add(san.split(":", 1)[1])')
        source = source.replace('"type": "dns", "value": d', '"type": "ip", "value": d')
        source = source.replace('order_payload = {"identifiers":', 'order_payload = {"profile": "shortlived", "identifiers":')
    write(root + '/tls/acme_tiny.py', source)
    http = f'''server {{
    listen 80;
    server_name {args.domain};
    location /.well-known/acme-challenge/ {{ root {root}/acme; }}
    location / {{ return 301 https://$host$request_uri; }}
}}
'''
    conf = '/etc/nginx/conf.d/yunyun-stage05.conf'
    # 首次仅启用HTTP验证路由；已有证书时直接保留HTTPS。
    check = subprocess.run([*ssh, f'test -s {root}/tls/fullchain.pem'])
    if check.returncode:
        write(conf, http, 0o644)
        run('nginx -t && systemctl reload nginx')
    run(f'test -f {root}/tls/account.key || (umask 077; openssl genrsa -out {root}/tls/account.key 4096)')
    run(f'test -f {root}/tls/domain.key || (umask 077; openssl genrsa -out {root}/tls/domain.key 2048)')
    san = ('IP:' if is_ip else 'DNS:') + args.domain
    subject = '/' if is_ip else '/CN=' + args.domain
    run(f'openssl req -new -sha256 -key {root}/tls/domain.key -subj {subject} -addext subjectAltName={san} -out {root}/tls/domain.csr')
    renewal_window = 172800 if is_ip else 2592000
    renewal = f'''#!/usr/bin/env bash
set -euo pipefail
if [[ -s {root}/tls/fullchain.pem ]] && openssl x509 -checkend {renewal_window} -noout -in {root}/tls/fullchain.pem; then exit 0; fi
python3 {root}/tls/acme_tiny.py --account-key {root}/tls/account.key --csr {root}/tls/domain.csr --acme-dir {root}/acme/.well-known/acme-challenge > {root}/tls/fullchain.next
openssl x509 -noout -in {root}/tls/fullchain.next
mv {root}/tls/fullchain.next {root}/tls/fullchain.pem
nginx -t
systemctl reload nginx
'''
    write(root + '/tls/renew.sh', renewal, 0o700)
    run(root + '/tls/renew.sh')
    https = f'''server {{
    listen 443 ssl;
    server_name {args.domain};
    ssl_certificate {root}/tls/fullchain.pem;
    ssl_certificate_key {root}/tls/domain.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 1100k;
    location / {{
        proxy_pass http://127.0.0.1:18005;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 180s;
    }}
}}
'''
    write(conf, http + https, 0o644)
    run('nginx -t && systemctl reload nginx')
    write('/etc/systemd/system/yunyun-stage05-renew.service', f'''[Unit]
Description=Renew Yunyun tutor TLS certificate
[Service]
Type=oneshot
ExecStart={root}/tls/renew.sh
''', 0o644)
    write('/etc/systemd/system/yunyun-stage05-renew.timer', '''[Unit]
Description=Daily Yunyun tutor certificate check
[Timer]
OnCalendar=daily
RandomizedDelaySec=3600
Persistent=true
[Install]
WantedBy=timers.target
''', 0o644)
    run('systemctl daemon-reload && systemctl enable --now yunyun-stage05-renew.timer')


if __name__ == '__main__':
    main()
