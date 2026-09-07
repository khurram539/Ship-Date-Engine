# TLS / SSL Certificates

How HTTPS is set up for `https://kplsh000.kaytheon.com:8000/` using an AWS Private Certificate Authority (ACM-PCA).

## Overview

- **Domain:** `kplsh000.kaytheon.com`
- **CA:** AWS Private CA (Root, RSA 2048, SHA256)
  - ARN: `arn:aws:acm-pca:us-east-1:396913703931:certificate-authority/161dc992-88b9-4d1d-995b-55197484b930`
  - Subject: `O=Kaytheon LLC, OU=Ship Data Engine`
  - CA expires: 2036-09-07
- **Server certificate:** issued 2026-09-07, **expires 2027-09-07** (365 days)
- **TLS termination:** done directly by the Python web server ([ship_date_engine/web.py](ship_date_engine/web.py)) via `--ssl-certfile` / `--ssl-keyfile`. TLS 1.2 minimum. No nginx/reverse proxy.
- **Status:** live and verified working from external clients as of 2026-09-07.

### Implementation notes

The TLS handshake is performed **per connection in the worker thread** (`TLSServer.finish_request` in [ship_date_engine/web.py](ship_date_engine/web.py)), with a 30-second socket timeout. Do not wrap the listening socket instead — an earlier version did that, and any client that opened a TCP connection without completing a handshake (port scanners, plain-HTTP requests) blocked the accept loop and froze the whole server (browser showed `ERR_TIMED_OUT` even though the process was healthy). Handshake failures from bad clients are silently ignored in `handle_error`.

## Certificate files

All cert material lives in `/home/kkhoja/tls/` (mode 700, owned by `kkhoja`). **Not stored in git.**

| File | Purpose |
|------|---------|
| `kplsh000.key` | Private key (RSA 2048, mode 600). Never share or commit. |
| `kplsh000.csr` | Certificate signing request (kept for renewals) |
| `kplsh000.crt` | Server certificate (leaf only) |
| `ca-chain.crt` | Private CA root certificate (distribute to clients) |
| `kplsh000-fullchain.crt` | Leaf + chain, used by the server |

## Server configuration

The systemd unit `/etc/systemd/system/ship-date-engine.service` runs:

```
ExecStart=/usr/bin/python3.11 -m ship_date_engine.web --host 0.0.0.0 --port 8000 \
  --ssl-certfile /home/kkhoja/tls/kplsh000-fullchain.crt \
  --ssl-keyfile /home/kkhoja/tls/kplsh000.key
```

Verify locally:

```bash
curl -s --cacert ~/tls/ca-chain.crt \
  --resolve kplsh000.kaytheon.com:8000:127.0.0.1 \
  https://kplsh000.kaytheon.com:8000/health
```

## Client trust

The CA is private, so browsers warn unless the root cert (`ca-chain.crt`) is installed on each client:

- **Windows:** double-click the file → Install Certificate → Local Machine → "Trusted Root Certification Authorities"
- **RHEL/Fedora:** `sudo cp ca-chain.crt /etc/pki/ca-trust/source/anchors/ && sudo update-ca-trust`
- **Debian/Ubuntu:** `sudo cp ca-chain.crt /usr/local/share/ca-certificates/kaytheon-ca.crt && sudo update-ca-certificates`
- **macOS:** Keychain Access → System → import → set to "Always Trust"

Clients must also resolve `kplsh000.kaytheon.com` (DNS or hosts-file entry).

The CA root is also installed in the **server's own trust store** (`/etc/pki/ca-trust/source/anchors/kaytheon-ca.crt`), so local `curl` works without `--cacert`.

### Testing from the server itself

The hostname resolves to the instance's public IP (`3.232.150.213`), which EC2 cannot reach from inside (no hairpin NAT) — a plain `curl https://kplsh000.kaytheon.com:8000/` from the server will hang. Always add `--resolve`:

```bash
curl -s --resolve kplsh000.kaytheon.com:8000:127.0.0.1 https://kplsh000.kaytheon.com:8000/health
```

[refresh_server.sh](refresh_server.sh) already does this for its health check.

## Renewal (before 2027-09-07)

The EC2 instance role `Ship-date-engine-ec2-role` has `acm-pca:IssueCertificate`, `GetCertificate`, and `GetCertificateAuthorityCertificate` on the CA, so renewal runs from this server:

```bash
CA_ARN=arn:aws:acm-pca:us-east-1:396913703931:certificate-authority/161dc992-88b9-4d1d-995b-55197484b930
cd ~/tls

# 1. Issue a new cert (reuses the existing key + CSR)
CERT_ARN=$(aws acm-pca issue-certificate \
  --certificate-authority-arn "$CA_ARN" \
  --csr fileb://kplsh000.csr \
  --signing-algorithm SHA256WITHRSA \
  --validity Value=365,Type=DAYS \
  --region us-east-1 \
  --query CertificateArn --output text)

# 2. Fetch the cert and chain (retry after a few seconds if not yet ready)
aws acm-pca get-certificate --certificate-authority-arn "$CA_ARN" \
  --certificate-arn "$CERT_ARN" --region us-east-1 \
  --query Certificate --output text > kplsh000.crt
aws acm-pca get-certificate --certificate-authority-arn "$CA_ARN" \
  --certificate-arn "$CERT_ARN" --region us-east-1 \
  --query CertificateChain --output text > ca-chain.crt
cat kplsh000.crt ca-chain.crt > kplsh000-fullchain.crt

# 3. Verify and restart
openssl x509 -in kplsh000.crt -noout -subject -dates
sudo systemctl restart ship-date-engine
curl -s --cacert ~/tls/ca-chain.crt \
  --resolve kplsh000.kaytheon.com:8000:127.0.0.1 \
  https://kplsh000.kaytheon.com:8000/health
```

To rotate the private key too, first regenerate the key + CSR, then run the steps above:

```bash
openssl req -new -newkey rsa:2048 -nodes \
  -keyout kplsh000.key -out kplsh000.csr \
  -subj "/O=Kaytheon LLC/OU=Ship Data Engine/CN=kplsh000.kaytheon.com" \
  -addext "subjectAltName=DNS:kplsh000.kaytheon.com"
chmod 600 kplsh000.key
```

## Troubleshooting

- **`AccessDeniedException` from ACM-PCA** — check the `AcmPcaIssueCert` statement on the `Ship-date-engine-ec2-role` IAM role. IAM changes can take a minute to propagate.
- **Browser "certificate not trusted"** — client is missing the CA root; see [Client trust](#client-trust).
- **curl hangs on the server** — hairpin NAT; see [Testing from the server itself](#testing-from-the-server-itself).
- **Browser `ERR_TIMED_OUT` while local checks pass** — first rule out the security group (`sg-06da2fa552524b2dd`, inbound TCP 8000); test from the client with `curl -vk https://kplsh000.kaytheon.com:8000/health`. If TCP connects but TLS stalls, suspect the accept-loop regression described in [Implementation notes](#implementation-notes).
- **Service won't start after cert change** — `journalctl -u ship-date-engine -n 50`; usually a bad path or unreadable key file.
- **`refresh_server.sh` refuses to run** — it requires a clean git tree; commit or stash local changes first.
