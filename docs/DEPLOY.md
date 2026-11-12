# Deploying SentinelOT to a Nebius AI Cloud VM

Written 6 October 2026. Commands for your Windows PC are PowerShell. Commands
for the VM are Linux (Ubuntu). Every step says where to run it.

Items marked **[VERIFY]** are things the sources could not confirm. Check them
in the console or the official rules before relying on them.

---

## 0. What you are building

```
Internet --> VM public IP (ports 80/443) --> Caddy container --> SentinelOT app container
                                                (HTTPS, proxy)    (FastAPI, port 8000, internal only)
```

- **Caddy** receives web traffic and, if you give it a domain name, gets and renews an HTTPS certificate by itself.
- The **app** is only reachable through Caddy. Its port 8000 is never opened to the internet.
- Results and the search cache live in a Docker volume, so they survive restarts.
- Your API keys live only in a `.env` file on the VM. They are not in the image or in git.

## 1. Facts that shape the plan

| Fact | Source |
|---|---|
| The default security group of a Nebius network allows **all** inbound and outbound traffic. It cannot be changed. | Nebius docs, VPC security groups |
| So the VM must be protected by its own firewall (UFW, step 5). | Consequence of the line above |
| In the console: Compute, Virtual machines, Create resource, Virtual machine. The wizard has Compute, Storage, Network, Configuration, Review steps. | Nebius docs, create a VM |
| Public IP can be dynamic or static. A dynamic address returns to the pool if the VM is stopped for more than one hour. A static address stays until the VM is deleted. | Nebius docs |
| Usernames `root` and `admin` are reserved and cannot be used for SSH. | Nebius docs |
| CPU-only platform `cpu-e2` (Intel Ice Lake) is in `eu-north1`. | Nebius docs, VM types |
| An example public boot image family is `ubuntu24.04-driverless`. | Nebius docs |
| Compute pricing is per vCPU-hour and per GiB-hour of RAM. The pricing page lists $0.012 per vCPU-hour and $0.0032 per GiB-hour. | Nebius docs, Compute pricing (the page lists several rate tables; **[VERIFY]** which applies to your platform) |

### Cost estimate (assumptions shown)

A 2 vCPU, 8 GiB VM at those rates: 2 x 0.012 + 8 x 0.0032 = about $0.05 per hour,
about $1.20 per day, about $36 per month, plus the disk. A third-party site gives
about $38.50 per month for a similar size, which agrees.

| Plan | Days | Estimate |
|---|---|---|
| Create VM on 20 Oct, keep until 15 Dec | about 56 | about $67 |
| Create VM today, keep until 15 Dec | about 70 | about $84 |

Your AI Cloud credit is $100. **[VERIFY]** the exact rates, the smallest
preset the console offers, and whether the credit has an expiry date.
**[VERIFY]** in the official hackathon rules whether the demo must stay online
during judging (1 to 15 December 2026). If it must, plan for the longer period.

---

## 2. Part A: prepare on your PC (about 15 minutes)

### A1. Install the deployment files and check the tests

Download `sentinelot_deploy.zip`, then in your `sentinelot` folder:

```powershell
$zip = Get-ChildItem "$env:USERPROFILE\Downloads\sentinelot_deploy*.zip" | Select-Object -First 1
Expand-Archive $zip.FullName -DestinationPath "$env:TEMP\dep" -Force
Copy-Item "$env:TEMP\dep\sentinelot_deploy\*" . -Recurse -Force
python -m pytest -q tests
```

Expect `16 passed`. The copy command also copies `.env.example`, `Dockerfile`,
`docker-compose.yml`, `Caddyfile` and `.dockerignore`.

### A2. Create a second Nebius API key for the server

In the Token Factory console, API keys, Create API key, name it `sentinelot-demo`.
Copy it straight into your password manager (it cannot be shown again).
Using a separate key means you can revoke the server key without breaking your laptop.

### A3. Commit

Check that `.env` is **not** listed, then commit:

```powershell
git status
git add .
git commit -m "Phase 3 web app and deployment files"
```

### A4. Make an SSH key (skip if you already have one)

```powershell
ssh-keygen -t ed25519 -C "sentinelot-demo"
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

Press Enter for the default file location. A passphrase is recommended.
The second command prints one long line starting with `ssh-ed25519`. You paste
that whole line into the console in step B1. Never share the file without `.pub`.

If `ssh-keygen` is not found, install the Windows optional feature "OpenSSH Client".

---

## 3. Part B: create the VM (about 15 minutes)

### B1. Console wizard

Open `console.nebius.com`, go to **Compute, Virtual machines, Create resource, Virtual machine**.

| Step | Choose |
|---|---|
| General or Compute | **Pay-as-you-go VM**. Platform: **Without GPUs**, type **Regular**. Platform `cpu-e2` (Intel Ice Lake) in `eu-north1` if offered. Choose the smallest preset that has at least 2 vCPU and 4 GiB RAM. |
| Settings | Project: your project. VM name: `sentinelot-demo`. |
| Storage | Boot disk: public **Ubuntu 24.04** image. Size: **30 GiB**. No extra disks. |
| Network | Default network and subnet. Public IP address: **Static** (so the address does not change). |
| Configuration | Username and SSH key, Create: username `sentinel` (not `root` or `admin`), paste your public key line, give it a name. |
| Review | Check, then **Create VM**. |

When the VM is running, open its page and copy the **Public IPv4** value. Below it is called `VM_IP`.

### B2. Connect

```powershell
ssh sentinel@VM_IP
```

Type `yes` the first time. You should get an Ubuntu prompt. Everything in Part C runs **on the VM**.

---

## 4. Part C: set up the VM

### C1. Firewall (do this first)

The Nebius default security group allows all inbound traffic, so UFW is your firewall.
Allow SSH **before** enabling it, or you will lock yourself out.

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### C2. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo docker --version
sudo docker compose version
```

Both version commands should print a version. This guide uses `sudo` with every
docker command, so you do not need to log out and in again.

---

## 5. Part D: upload and start the app

### D1. Upload the code (on your PC)

`git archive` packs only committed files, so `.env`, `.venv` and your caches are not included.

```powershell
cd C:\Users\Lenovo\Desktop\OT_LAB\sentinelot_starter\sentinelot
git archive --format=tar.gz -o sentinelot.tar.gz HEAD
scp sentinelot.tar.gz sentinel@VM_IP:~/
```

### D2. Unpack and configure (on the VM)

```bash
mkdir -p ~/sentinelot
tar xzf ~/sentinelot.tar.gz -C ~/sentinelot
cd ~/sentinelot
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
nano .env
```

In `nano`, fill in the file. The model lines are the same ones you use locally.

```
NEBIUS_API_KEY=<the sentinelot-demo key from A2>
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
TAVILY_API_KEY=<your Tavily key>
APP_ADMIN_TOKEN=<the random string printed above>
MODEL_INTAKE=nvidia/nemotron-3-super-120b-a12b
MODEL_INTEL=nvidia/nemotron-3-super-120b-a12b
MODEL_MAPPER=nvidia/nemotron-3-super-120b-a12b
MODEL_TRIAGE=nvidia/Nemotron-3-Ultra-550b-a55b
MODEL_ADVISOR=nvidia/nemotron-3-super-120b-a12b
DEMO_PER_IP_HOUR=10
DEMO_DAILY_CAP=200
SITE_ADDRESS=:80
```

Save with Ctrl+O, Enter, then exit with Ctrl+X. Then lock the file down:

```bash
chmod 600 .env
```

`DEMO_DAILY_CAP=200` limits public runs to 200 per day. At about one cent per run
that is roughly $2 per day of Token Factory credit at most. Lower it if you want a safer margin.

### D3. Start

```bash
sudo docker compose up -d --build
sudo docker compose ps
```

The first build takes a few minutes. When it finishes, both `app` and `caddy`
should be running (the app shows `healthy` after about 30 seconds).

### D4. Test

On your PC, open `http://VM_IP` in a browser. You should see SentinelOT.
Run scenario S01. Then open it from your phone on mobile data as well, to
prove it is reachable from outside your own network.

---

## 6. Part E: HTTPS (recommended)

HTTPS needs a domain name. Plain `http://IP` works for judges but browsers mark it "Not secure".

1. Get a domain, or a subdomain of one you own. In its DNS settings, add an **A record** pointing at `VM_IP`.
2. Wait until it resolves: `nslookup demo.yourdomain.com` should print `VM_IP`.
3. On the VM, in `~/sentinelot`, edit `.env` and set `SITE_ADDRESS=demo.yourdomain.com`.
4. Apply it:

   ```bash
   sudo docker compose up -d
   sudo docker compose logs caddy | tail -30
   ```

Caddy obtains the certificate by itself, which needs ports 80 and 443 reachable from
the internet. The log should mention a certificate being obtained. Then open
`https://demo.yourdomain.com`.

No domain yet? Stay on `SITE_ADDRESS=:80`.

---

## 7. Updating the app later

On your PC:

```powershell
git add .
git commit -m "describe the change"
git archive --format=tar.gz -o sentinelot.tar.gz HEAD
scp sentinelot.tar.gz sentinel@VM_IP:~/
```

On the VM:

```bash
cd ~/sentinelot
tar xzf ~/sentinelot.tar.gz -C ~/sentinelot
sudo docker compose up -d --build
```

Your `.env` is kept, because it is never in the archive. Saved results are kept
in the Docker volume.

## 8. Everyday commands (on the VM)

| Task | Command |
|---|---|
| Status | `sudo docker compose ps` |
| App logs | `sudo docker compose logs -f app` |
| Caddy logs | `sudo docker compose logs caddy` |
| Restart | `sudo docker compose restart` |
| Stop | `sudo docker compose down` |
| Disk space | `df -h /` |

## 9. Troubleshooting

| Symptom | What to check |
|---|---|
| `ssh` says permission denied | Username must match the one in the console, and the key must be the one you pasted. |
| Browser cannot connect to `VM_IP` | `sudo ufw status` must show 80 and 443 allowed. `sudo docker compose ps` must show `caddy` running. |
| Page loads but runs fail | `sudo docker compose logs app`. A 401 or model error means a wrong key or model ID in `.env`. |
| "Limit reached" message | Raise `DEMO_PER_IP_HOUR` or `DEMO_DAILY_CAP` in `.env`, then `sudo docker compose up -d`. |
| HTTPS certificate fails | The A record must point at `VM_IP` and ports 80 and 443 must be open. Read `sudo docker compose logs caddy`. |
| All visitors share one rate limit | The app reads the visitor address from the `X-Forwarded-For` header Caddy sets. This is already switched on in `docker-compose.yml` (`TRUST_PROXY`). |

## 10. Keeping costs under control

- Check the console's billing page after the first day and compare with the estimate in section 1.
- A stopped VM may still be billed for its disk **[VERIFY]**. Delete the VM and its disk when judging is over.
- Never publish your repository with `.env` in it. If a key was ever committed, rotate it.
