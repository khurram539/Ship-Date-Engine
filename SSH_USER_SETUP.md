# RHEL 10 User Setup Guide for kkhoja

This document provides step-by-step instructions for creating and configuring the `kkhoja` user on a new RHEL 10 server with SSH key authentication.

**Last Updated:** August 10, 2026  
**Server:** RHEL 10 EC2 Instance (ip-172-31-39-148 / public IP: 98.91.242.163)  
**User:** kkhoja (UID: 1001, GID: 1001)

---

## Quick Start (All Commands at Once)

```bash
# 1. Create user and add to wheel group
useradd -m -s /bin/bash kkhoja
usermod -aG wheel kkhoja

# 2. Copy ec2-user's key to kkhoja
cp /home/ec2-user/.ssh/authorized_keys /home/kkhoja/.ssh/authorized_keys

# 3. Fix permissions (CRITICAL)
chown -R kkhoja:kkhoja /home/kkhoja/.ssh
chmod 700 /home/kkhoja/.ssh
chmod 600 /home/kkhoja/.ssh/authorized_keys

# 4. Enable password auth and restart SSH
sed -i '/^PasswordAuthentication no/d' /etc/ssh/sshd_config
systemctl restart sshd

# 5. Disable SELinux temporarily
setenforce 0
```

Then connect from your local PuTTY: `98.91.242.163` port 22, username `kkhoja`

---

## Detailed Step-by-Step Guide

### Prerequisites

- Root access to your RHEL 10 server (via console, AWS EC2 instance connect, or existing SSH)
- Your SSH private key file (`.pem` or `.ppk`) from PuTTY/OpenSSH
- Local machine with PuTTY and/or OpenSSH client installed

---

### Step 1: Create the User

```bash
# Create user with home directory and bash shell as default
useradd -m -s /bin/bash kkhoja

# Add user to wheel group for sudo privileges
usermod -aG wheel kkhoja

# Verify user creation
id kkhoja
groups kkhoja

# Expected output:
# uid=1001(kkhoja) gid=1001(kkhoja) groups=1001(kkhoja),10(wheel)
```

**Explanation:**
- `-m`: Creates home directory at `/home/kkhoja`
- `-s /bin/bash`: Sets bash as default shell
- `wheel`: Group with sudo privileges on RHEL/CentOS

---

### Step 2: Set Up SSH Key Authentication

#### Option A: Copy from ec2-user's Key (Recommended if already set up)

```bash
# Copy ec2-user's authorized_keys to kkhoja
cat /home/ec2-user/.ssh/authorized_keys > /home/kkhoja/.ssh/authorized_keys
```

#### Option B: Generate New Key Pair on Server

```bash
# Generate ed25519 key (modern and fast) - run as root
ssh-keygen -t ed25519 -f /root/.ssh/kkhoja_key -C "kkhoja@server" -N ""

# Copy public key to kkhoja's authorized_keys
cat /root/.ssh/kkhoja_key.pub > /home/kkhoja/.ssh/authorized_keys

# OR generate RSA key (more compatible)
ssh-keygen -t rsa -b 4096 -f /root/.ssh/kkhoja_rsa -C "kkhoja@server" -N ""
cat /root/.ssh/kkhoja_rsa.pub > /home/kkhoja/.ssh/authorized_keys
```

---

### Step 3: Configure Permissions (CRITICAL)

**This step is essential for SSH to work correctly.**

```bash
# Create .ssh directory if it doesn't exist
mkdir -p /home/kkhoja/.ssh

# Set correct ownership and permissions IMMEDIATELY
chown kkhoja:kkhoja /home/kkhoja/.ssh
chmod 700 /home/kkhoja/.ssh

# Set authorized_keys permissions
chmod 600 /home/kkhoja/.ssh/authorized_keys

# Verify permissions - run this to check everything is correct:
ls -la /home/kkhoja/.ssh/

# Expected output:
# drwx------. 2 kkhoja kkhoja ... .ssh
# -rw-------. 1 kkhoja kkhoja ... authorized_keys
```

**Why these permissions matter:**
- `.ssh` directory must be `700` (owner only) or SSH will reject all keys
- `authorized_keys` must be `600` (owner read/write only)
- Ownership must match the user (kkhoja:kkhoja), not root

---

### Step 4: Configure SSH Server (`sshd_config`)

Edit the SSH server configuration:

```bash
vi /etc/ssh/sshd_config
```

**Required settings** (ensure these lines exist and have NO `#` comment at the start):

```
PasswordAuthentication yes           # Enable for initial testing (change to no later)
PermitEmptyPasswords no              # Security setting - never allow empty passwords
UsePAM yes                           # Allow PAM authentication
PubkeyAuthentication yes             # Enable key-based authentication
ChallengeResponseAuthentication no   # Disable password challenges
AuthorizedKeysFile .ssh/authorized_keys  # Default file location
```

**To remove conflicting lines:**

```bash
# Remove any duplicate PasswordAuthentication "no" lines
sed -i '/^PasswordAuthentication no/d' /etc/ssh/sshd_config

# Verify only "yes" remains
grep "^PasswordAuthentication" /etc/ssh/sshd_config
# Should output: PasswordAuthentication yes
```

**Save and restart SSH service:**

```bash
systemctl restart sshd
systemctl status sshd | head -5

# Expected output:
# Active: active (running) since ...
```

---

### Step 5: Handle SELinux (RHEL Specific)

RHEL uses SELinux which can block SSH key authentication by default.

#### For Development/Testing:

```bash
# Temporarily set to permissive mode
setenforce 0

# Verify status
getenforce
# Expected output: Permissive
```

#### For Production (if needed):

If you must keep SELinux in enforcing mode, fix the context first:

```bash
restorecon -Rv /home/kkhoja/.ssh/
```

---

### Step 6: Test the Connection

#### From Your Local Machine (PuTTY):

1. **Open PuTTY**
   - Host Name/IP: Your EC2 public IP (e.g., `98.91.242.163`)
   - Port: `22`
   - Connection type: `SSH`
   - Username: `kkhoja`

2. **Under Connection → SSH → Auth:**
   - Click "Browse" and load your private key (`.ppk` file)
   - Or try connecting WITHOUT a key first to test password authentication

3. **Click "Open"** and attempt connection

#### Expected Results:

- ✅ **Successful** - You get a bash prompt as `kkhoja`
- ✅ Password auth works if you haven't loaded a key
- ✅ SSH key auth works after loading the .ppk file

---

## Troubleshooting

### Problem 1: "Server refused our key"

**Cause:** Key mismatch, wrong permissions, or SELinux blocking

**Solution:**

```bash
# Check permissions first
ls -la /home/kkhoja/.ssh/
ls -la /home/kkhoja/.ssh/authorized_keys

# Should show:
# drwx------. 2 kkhoja kkhoja ... .ssh
# -rw-------. 1 kkhoja kkhoja ... authorized_keys

# Fix with:
chown -R kkhoja:kkhoja /home/kkhoja/.ssh
chmod 700 /home/kkhoja/.ssh
chmod 600 /home/kkhoja/.ssh/authorized_keys

# Check SELinux status
getenforce
# If Enforcing, temporarily disable:
setenforce 0

# Restart SSH
systemctl restart sshd
```

---

### Problem 2: "Connection refused"

**Cause:** AWS Security Group or firewall blocking port 22

**Solution:**

1. **Check AWS EC2 Console:**
   - Go to EC2 Dashboard → Security Groups
   - Find the security group attached to your instance
   - Check Inbound Rules tab

2. **Add SSH Rule if missing:**
   | Type     | Port Range | Source      | Allow |
   |----------|------------|-------------|-------|
   | SSH      | 22         | `0.0.0.0/0` or your public IP | ✓     |

3. **On RHEL server, verify firewall:**
```bash
systemctl status firewalld
firewall-cmd --list-all
# Ensure SSH service is allowed:
firewall-cmd --permanent --add-service=ssh
firewall-cmd --reload
```

---

### Problem 3: "Permission denied (publickey)"

**Cause:** SELinux blocking authentication, incorrect key format, or wrong file permissions

**Solution:**

```bash
# Temporarily disable SELinux for testing
setenforce 0

# Restart SSH service
systemctl restart sshd

# Verify your public key in authorized_keys matches private key
cat /home/kkhoja/.ssh/authorized_keys
# Should start with: ssh-rsa ... or ssh-ed25519 ...

# If using PPK file from PuTTY:
# 1. Open PuTTYgen and load your .ppk file
# 2. Conversions → Save public key (saves to text format)
# 3. Paste that text into authorized_keys on server
```

---

### Problem 4: Key format mismatch (PPK vs PEM)

**Cause:** PuTTY's .ppk format is binary/proprietary, OpenSSH expects text PEM format

**Solution:**

1. **On your local Windows machine:**
   - Open PuTTYgen
   - Load your `.ppk` file (e.g., `Khurram-key.ppk`)
   - Go to **Conversions → Save public key**
   - Save as a text file (e.g., `temp_pubkey.pub`)
   - Copy the entire content (starts with `ssh-rsa` or `ssh-ed25519`)

2. **On your RHEL server:**
   ```bash
   # Replace YOUR_PUBLIC_KEY_HERE with the actual key from PuTTYgen
   cat > /home/kkhoja/.ssh/authorized_keys << 'EOF'
   ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC... kkhoja@local
   EOF
   
   chown kkhoja:kkhoja /home/kkhoja/.ssh/authorized_keys
   chmod 600 /home/kkhoja/.ssh/authorized_keys
   ```

---

### Problem 5: Can't find your key in PuTTY

**Cause:** Key file path or format issue

**Solution:**

1. **Verify the .ppk file exists locally:**
   ```cmd
   dir C:\path\to\Khurram-key.ppk
   ```

2. **In PuTTY configuration (Session → Auth):**
   - Click "Browse"
   - Navigate to and select your `.ppk` file
   - Verify it loads successfully (shows key info)

3. **Alternative: Use OpenSSH command line instead of PuTTY:**
   If you have WSL or another Linux machine nearby, convert your PPK first, then use:
   ```bash
   ssh -i /path/to/converted/key.pem kkhoja@98.91.242.163
   ```

---

## Optional: Enable Sudo Access

The user is already in the `wheel` group during setup, which grants sudo privileges on RHEL. Verify it works:

```bash
# Connect as kkhoja via SSH first
ssh kkhoja@98.91.242.163

# Then test sudo access:
sudo whoami
# Expected output: root
```

---

## Security Hardening (Post-Setup)

After confirming everything works, apply these security measures:

### 1. Disable Password Authentication (Force Key-Only Auth)

```bash
vi /etc/ssh/sshd_config
# Find and change this line:
PasswordAuthentication no

systemctl restart sshd
```

### 2. Set Up Fail2Ban for Brute-Force Protection

```bash
yum install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

### 3. Re-enable SELinux (if you disabled it) and fix contexts properly

```bash
setenforce 1
restorecon -Rv /home/kkhoja/.ssh/
```

---

## Quick Reference Commands

### Create User Fresh
```bash
useradd -m -s /bin/bash kkhoja
usermod -aG wheel kkhoja
```

### Add Public Key (from ec2-user)
```bash
cp /home/ec2-user/.ssh/authorized_keys /home/kkhoja/.ssh/authorized_keys
```

### Fix Permissions
```bash
chown -R kkhoja:kkhoja /home/kkhoja/.ssh
chmod 700 /home/kkhoja/.ssh
chmod 600 /home/kkhoja/.ssh/authorized_keys
```

### Restart and Configure SSH
```bash
sed -i '/^PasswordAuthentication no/d' /etc/ssh/sshd_config
systemctl restart sshd
```

### Temporarily Disable SELinux (Testing Only)
```bash
setenforce 0
getenforce  # Should show "Permissive"
```

---

## Summary Checklist

Use this checklist to verify your setup:

- [x] User `kkhoja` created with home directory `/home/kkhoja`
- [x] User added to `wheel` group (sudo privileges)
- [x] `.ssh` directory exists with permissions `700` owned by `kkhoja:kkhoja`
- [x] `authorized_keys` file contains public key with permissions `600`
- [x] SSH server configured (`PasswordAuthentication yes` for testing)
- [x] SELinux set to permissive mode for development
- [x] SSH service restarted and running
- [x] Successfully connected from local PuTTY/SSH client as `kkhoja`
- [ ] (Optional) Verified sudo access works
- [ ] (Optional) Applied security hardening (disable password, enable fail2ban)

---

## Files Created/Modified

**Created:**
- `/home/kkhoja/` - User home directory (`755` permissions default)
- `/home/kkhoja/.bash_profile` - Bash profile configuration
- `/home/kkhoja/.bashrc` - Bash rc configuration
- `/home/kkhoja/.ssh/` - SSH key directory (`700` permissions)
- `/home/kkhoja/.ssh/authorized_keys` - Public keys for authentication (`600` permissions, `root:root` or user-owned)

**Modified:**
- `/etc/ssh/sshd_config` - SSH server configuration (PasswordAuthentication, PubkeyAuthentication, etc.)
- `/etc/group` - Added kkhoja to wheel group

---

## Connection Information

| Parameter     | Value                      |
|---------------|----------------------------|
| **Hostname**  | `98.91.242.163`            |
| **Private IP**| `ip-172-31-39-148`         |
| **Port**      | `22`                       |
| **Username**  | `kkhoja`                   |
| **Key File**  | `Khurram-key.ppk` (or PEM) |
| **SSH Client**| PuTTY / OpenSSH client     |

---

## Contact & Support

For issues not covered here, check:

1. **AWS EC2 Console:**
   - Check instance status and security group rules
   - Verify public IP is accessible from your network

2. **RHEL Documentation:**
   - [SELinux Contexts](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/managing_selinux_contexts/)
   - [OpenSSH Troubleshooting](https://linux.die.net/man/5/sshd_config)

3. **Network Issues:**
   - Use `telnet 98.91.242.163 22` or `Test-NetConnection` from local machine
   - Check AWS Security Group inbound rules allow port 22

---

**Setup Completed Successfully on: August 10, 2026**  
**Verified by:** kkhoja user can log in via PuTTY at `98.91.242.163`