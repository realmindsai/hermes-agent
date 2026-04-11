# Google Workspace MCP Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire hermes-dee and hermes-tracy to the Google Workspace MCP servers already running on totoro, giving both bots Gmail + Calendar + Drive + Docs + Sheets + Contacts access.

**Architecture:** Two `@dguido/google-workspace-mcp` HTTP services already run on totoro (ports 3102 and 3202), one per user account. Each Hermes container connects via the Docker bridge at `172.17.0.1`. No new services need to be built — only Tracy's workspace service needs to be started, two config files need a new MCP entry, and redundant legacy services need to be decommissioned after testing.

**Tech Stack:** systemd (service management), YAML (Hermes config), `deploy/deploy.sh` (deployment), `ssh totoro` / `ssh totoro_ts` (remote access)

---

## Chunk 1: Activate service, update configs, deploy

### Task 1: Start Tracy's workspace MCP service on totoro

**Files:** none (remote service management only)

- [ ] **Step 1: Enable and start the service**

```bash
ssh totoro "sudo systemctl enable --now google-workspace-mcp-tracy.service"
```

Expected output: no error, prompt returns.

- [ ] **Step 2: Verify it is running**

```bash
ssh totoro "systemctl is-active google-workspace-mcp-tracy.service"
```

Expected: `active`

- [ ] **Step 3: Verify the HTTP endpoint responds**

```bash
ssh totoro "curl -s --max-time 10 -X POST http://localhost:3202/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1\"}}}' \
  2>&1"
```

Expected: output contains `google-workspace-mcp` (the server name in the JSON-RPC response). The response arrives as an SSE stream so multiple `event:`/`data:` lines are normal.

---

### Task 2: Add workspace MCP entry to Dee's config

**Files:**
- Modify: `deploy/config-dee.yaml`

- [ ] **Step 1: Add the workspace entry**

In `deploy/config-dee.yaml`, append under the `mcp_servers:` block (after the `ms365` entry):

```yaml
  workspace:
    url: "http://172.17.0.1:3102/mcp"
```

The full `mcp_servers` block should look like:

```yaml
mcp_servers:
  jot:
    url: "http://172.17.0.1:8768/mcp"
    headers:
      Authorization: "Bearer ${JOT_TOKEN}"
  kb:
    url: "http://172.17.0.1:8767/mcp"
    headers:
      Authorization: "Bearer ${JOT_TOKEN}"
  ms365:
    url: "http://172.17.0.1:8765/mcp"
    headers:
      Authorization: "Bearer ${JOT_TOKEN}"
  workspace:
    url: "http://172.17.0.1:3102/mcp"
```

---

### Task 3: Add workspace MCP entry to Tracy's config

**Files:**
- Modify: `deploy/config-tracy.yaml`

- [ ] **Step 1: Add the workspace entry**

In `deploy/config-tracy.yaml`, append under the `mcp_servers:` block (after the `ms365` entry):

```yaml
  workspace:
    url: "http://172.17.0.1:3202/mcp"
```

- [ ] **Step 2: Commit both configs together**

```bash
git add deploy/config-dee.yaml deploy/config-tracy.yaml
git commit -m "feat(config): add Google Workspace MCP server for dee and tracy"
```

---

### Task 4: Deploy both instances

**Files:** none (runs deploy pipeline)

- [ ] **Step 1: Run deploy script**

From the repo root:

```bash
./deploy/deploy.sh totoro_ts both
```

Expected: script completes with `=== Deploy complete ===`. During execution you will see `active` printed once per instance after each restart — that is the per-instance health check, not a final summary line.

- [ ] **Step 2: Confirm workspace tools registered in Dee's container**

```bash
ssh totoro "docker logs hermes-dee 2>&1 | grep -i workspace | head -10"
```

Expected: lines showing workspace tools being registered (e.g. `mcp_workspace_*` tool names or similar registration log entries from `mcp_tool.py`).

- [ ] **Step 3: Confirm workspace tools registered in Tracy's container**

```bash
ssh totoro "docker logs hermes-tracy 2>&1 | grep -i workspace | head -10"
```

Expected: same as above for Tracy's container.

---

## Chunk 2: Smoke tests + cleanup

### Task 5: Smoke test Dee's bot

**Files:** none (manual interaction)

- [ ] **Step 1: Ask Dee's bot to read most recent email**

In Dee's Telegram bot, send:

> What is my most recent email?

Expected: bot responds with a summary of Dee's most recent Gmail message.

- [ ] **Step 2: Ask Dee's bot to list today's calendar events**

In Dee's Telegram bot, send:

> What do I have on my calendar today?

Expected: bot responds with Dee's calendar events for today (or "nothing scheduled" if the calendar is empty).

---

### Task 6: Smoke test Tracy's bot

**Files:** none (manual interaction)

- [ ] **Step 1: Ask Tracy's bot to read most recent email**

In Tracy's Telegram bot, send:

> What is my most recent email?

Expected: bot responds with a summary of Tracy's most recent Gmail message (deeperdailylife@gmail.com account).

- [ ] **Step 2: Ask Tracy's bot to list today's calendar events**

In Tracy's Telegram bot, send:

> What do I have on my calendar today?

Expected: bot responds with Tracy's calendar events for today.

---

### Task 7: Decommission redundant services

Only run this task after Tasks 5 and 6 pass.

**Files:** none (remote service management)

- [ ] **Step 1: Disable redundant services on totoro**

```bash
ssh totoro "sudo systemctl disable --now gmail-mcp.service gmail-mcp-tracy.service google-calendar-mcp.service google-calendar-mcp-tracy.service"
```

Expected: all four services report `Removed` or `Disabled`. No errors.

- [ ] **Step 2: Verify all four are stopped**

```bash
ssh totoro "systemctl is-active gmail-mcp.service gmail-mcp-tracy.service google-calendar-mcp.service google-calendar-mcp-tracy.service"
```

Expected: four lines each reading `inactive` or `failed` (disabled services show `inactive`).

- [ ] **Step 3: Commit final state note**

```bash
git commit --allow-empty -m "ops: decommission redundant gmail/calendar MCP services on totoro

google-workspace-mcp covers Gmail + Calendar for both dee and tracy.
Disabled: gmail-mcp, gmail-mcp-tracy, google-calendar-mcp, google-calendar-mcp-tracy."
```
