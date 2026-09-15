# Secure ECS Admin Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace changing-public-IP security-group access with verified Tailscale private access while preserving the public dashboard and Workbench recovery path.

**Architecture:** Install Tailscale on the Windows client and Alibaba Cloud Linux ECS, join both to one tailnet, verify all management paths over the overlay, and only then remove public management-port rules. Public HTTP remains independent from the administration plane.

**Tech Stack:** Windows 11, winget, Tailscale, Alibaba Cloud Linux 3, Alibaba Cloud Workbench, ECS security groups, OpenSSH

**Spec:** `docs/superpowers/specs/2026-09-15-secure-ecs-admin-access-design.md`

## Global Constraints

- Preserve `100.104.0.0/16 -> TCP 22` as the Workbench recovery path.
- Preserve public TCP 80 for the portfolio dashboard.
- Do not expose TCP 22 to `0.0.0.0/0`.
- Do not remove any security-group rule before private-path verification succeeds.
- Do not automate authentication prompts or store credentials/tokens.
- Require action-time user confirmation before removing cloud firewall rules.
- Do not purchase or confirm the ECS memory upgrade in this plan.

---

### Task 1: Windows private-network endpoint

**Files:**
- Modify: none (system package installation only)

**Interfaces:**
- Consumes: Windows administrator package installation capability
- Produces: `tailscale.exe`, a logged-in Windows tailnet node, and a Windows Tailscale IPv4

- [ ] **Step 1: Confirm Tailscale is absent and winget is available**

Run: `Get-Command tailscale, winget -ErrorAction SilentlyContinue`

Expected: `winget.exe` is present; Tailscale may be absent.

- [ ] **Step 2: Install the official Tailscale package**

Run: `winget install --id Tailscale.Tailscale --exact --accept-package-agreements --accept-source-agreements`

Expected: winget reports a successful install from the configured source.

- [ ] **Step 3: Start login without embedding credentials**

Run: `& "$env:ProgramFiles\Tailscale\tailscale.exe" up`

Expected: Tailscale opens or prints an interactive authentication URL; the user completes authentication personally.

- [ ] **Step 4: Verify Windows tailnet state**

Run: `& "$env:ProgramFiles\Tailscale\tailscale.exe" status; & "$env:ProgramFiles\Tailscale\tailscale.exe" ip -4`

Expected: Windows is listed online and has a `100.x.y.z` Tailscale IPv4.

### Task 2: ECS private-network endpoint

**Files:**
- Modify: none (server package/service installation only)

**Interfaces:**
- Consumes: one manual paste in Alibaba Cloud Workbench and user-completed browser authentication
- Produces: running `tailscaled`, logged-in ECS tailnet node, and ECS Tailscale IPv4

- [ ] **Step 1: Install Tailscale from its official Linux installer in Workbench**

Paste in Workbench:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Expected: the installer identifies Alibaba Cloud Linux/RHEL-compatible packaging and installs `tailscale` plus `tailscaled`.

- [ ] **Step 2: Enable and start the service**

Paste in Workbench:

```bash
sudo systemctl enable --now tailscaled
sudo systemctl is-active tailscaled
```

Expected: `active`.

- [ ] **Step 3: Join the tailnet without a reusable auth key**

Paste in Workbench:

```bash
sudo tailscale up
```

Expected: a one-time authentication URL is printed; the user opens it and authorizes the ECS node.

- [ ] **Step 4: Return the ECS private address**

Paste in Workbench:

```bash
tailscale ip -4
tailscale status
```

Expected: a `100.x.y.z` ECS address and both nodes visible as online.

### Task 3: End-to-end verification

**Files:**
- Modify: none

**Interfaces:**
- Consumes: ECS Tailscale IPv4 from Task 2
- Produces: evidence that the private path is safe to make authoritative

- [ ] **Step 1: Check private TCP reachability from Windows**

Read the ECS Tailscale address once and test each required port:

```powershell
$ecsTsIp = Read-Host 'ECS Tailscale IPv4'
22,80,9870,8088,9160,3306 | ForEach-Object {
  $port = $_
  $reachable = Test-NetConnection -ComputerName $ecsTsIp -Port $port -InformationLevel Quiet
  [pscustomobject]@{Port=$port; Reachable=$reachable}
}
```

Expected: TCP 22 is reachable; management ports match the services currently listening on the ECS. A closed port is diagnosed on-host before any security-group change.

- [ ] **Step 2: Verify Hadoop and panel pages in the browser**

Open `http://$ecsTsIp:9870`, `http://$ecsTsIp:8088`, and `http://$ecsTsIp:9160` using the address recorded in Step 1.

Expected: the listening services load over Tailscale. Authentication remains required where configured.

- [ ] **Step 3: Verify SSH path**

Run: `ssh hadoop@$ecsTsIp "hostname; tailscale ip -4"`

Expected: the ECS hostname and same Tailscale IPv4 are returned.

- [ ] **Step 4: Verify recovery and public application paths**

Expected: Alibaba Cloud Workbench still opens, and `http://116.62.152.97/` still loads.

### Task 4: Security-group convergence

**Files:**
- Modify: none (Alibaba Cloud security-group rules only)

**Interfaces:**
- Consumes: passing Task 3 evidence and explicit user confirmation for the exact rules
- Produces: no public ingress to TCP 9870, 8088, 9160, or 3306

- [ ] **Step 1: Inventory exact candidate rules without editing**

Candidate set: every public-client IPv4/IPv6 ingress rule whose destination is TCP `9870`, `8088`, `9160`, or `3306`, including stale personal, school, company, and panel ranges. Exclude TCP 80 and `100.104.0.0/16 -> TCP 22`.

Expected: a screenshot or readback of the exact rule IDs/sources/ports.

- [ ] **Step 2: Obtain action-time confirmation**

Present the exact candidate set and state: removal can temporarily block those public management URLs; Workbench and Tailscale remain available.

Expected: the user explicitly confirms this exact removal batch.

- [ ] **Step 3: Remove only the confirmed rules**

Expected: no ingress rule for TCP 9870, 8088, 9160, or 3306 remains accessible from public client addresses; TCP 80 and Workbench SSH remain unchanged.

- [ ] **Step 4: Run positive and negative verification**

Run private checks from Task 3 again. Separately test public endpoints `116.62.152.97:9870`, `:8088`, `:9160`, and `:3306`.

Expected: private Tailscale access succeeds; public management endpoints fail; the public dashboard and Workbench succeed.

- [ ] **Step 5: Commit documentation only**

Run:

```powershell
git add docs/superpowers/specs/2026-09-15-secure-ecs-admin-access-design.md docs/superpowers/plans/2026-09-15-secure-ecs-admin-access.md
git commit -m "docs: plan secure ECS administration access"
```

Expected: one documentation-only commit; unrelated untracked files remain untouched.
