# Telegram Parakeet STT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `hermes-dee` transcribe inbound Telegram audio through Totoro's host `parakeet-stt` service without changing Tracy or the default STT fallback chain.

**Architecture:** Add a dedicated `parakeet` provider to the shared transcription module, then point Dee's deploy config at Totoro's host bridge endpoint. Keep Telegram media caching and gateway enrichment unchanged, because that path already exists and is the correct seam.

**Tech Stack:** Python 3.12, `httpx`, `pytest`, YAML deploy config, Telegram gateway, Docker bridge networking

---

### Task 1: Write the provider tests first

**Files:**
- Modify: `tests/tools/test_transcription_tools.py`
- Modify: `tests/hermes_cli/test_totoro_deploy_config.py`
- Create: `tests/integration/test_totoro_parakeet_stt_contract.py`
- Create: `tests/e2e/test_totoro_parakeet_stt_contract.py`

- [ ] **Step 1: Write the failing unit tests for provider selection and HTTP transcription**

```python
def test_explicit_parakeet_provider_selected():
    with patch("tools.transcription_tools._has_parakeet_backend", return_value=True):
        from tools.transcription_tools import _get_provider
        assert _get_provider({"provider": "parakeet"}) == "parakeet"


def test_explicit_parakeet_without_base_url_returns_none():
    with patch("tools.transcription_tools._has_parakeet_backend", return_value=False):
        from tools.transcription_tools import _get_provider
        assert _get_provider({"provider": "parakeet"}) == "none"


def test_dispatches_to_parakeet(sample_ogg):
    config = {"provider": "parakeet", "parakeet": {"base_url": "http://172.17.0.1:8770"}}
    with patch("tools.transcription_tools._load_stt_config", return_value=config), \
         patch("tools.transcription_tools._get_provider", return_value="parakeet"), \
         patch("tools.transcription_tools._transcribe_parakeet",
               return_value={"success": True, "transcript": "hi", "provider": "parakeet"}) as mock_parakeet:
        from tools.transcription_tools import transcribe_audio
        result = transcribe_audio(sample_ogg)

    assert result["provider"] == "parakeet"
    mock_parakeet.assert_called_once()
```

- [ ] **Step 2: Write the failing unit tests for Parakeet response handling**

```python
def test_parakeet_successful_transcription(sample_ogg):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"text": "hello from parakeet"}

    with patch("httpx.post", return_value=response) as mock_post:
        from tools.transcription_tools import _transcribe_parakeet
        result = _transcribe_parakeet(sample_ogg, "ignored")

    assert result == {
        "success": True,
        "transcript": "hello from parakeet",
        "provider": "parakeet",
    }
    mock_post.assert_called_once()


def test_parakeet_empty_text_returns_failure(sample_ogg):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"text": ""}

    with patch("httpx.post", return_value=response):
        from tools.transcription_tools import _transcribe_parakeet
        result = _transcribe_parakeet(sample_ogg, "ignored")

    assert result["success"] is False
    assert "empty transcript" in result["error"].lower()
```

- [ ] **Step 3: Write the failing deploy contract tests**

```python
def test_hermes_dee_uses_parakeet_stt():
    dee_config = _load_yaml("deploy/config-dee.yaml")

    assert dee_config["stt"]["provider"] == "parakeet"
    assert dee_config["stt"]["parakeet"]["base_url"] == "http://172.17.0.1:8770"


def test_dee_parakeet_contract_is_consistent():
    dee_config = _load_yaml("deploy/config-dee.yaml")

    assert dee_config["stt"]["provider"] == "parakeet"
    assert dee_config["stt"]["parakeet"]["base_url"] == "http://172.17.0.1:8770"
```

- [ ] **Step 4: Run the red test set and confirm it fails for missing Parakeet support**

Run:

```bash
source .venv/bin/activate && pytest \
  tests/tools/test_transcription_tools.py \
  tests/hermes_cli/test_totoro_deploy_config.py \
  tests/integration/test_totoro_parakeet_stt_contract.py \
  tests/e2e/test_totoro_parakeet_stt_contract.py -q
```

Expected: failures mentioning missing `parakeet` provider handling and missing Dee deploy config.

### Task 2: Implement the minimal Parakeet provider

**Files:**
- Modify: `tools/transcription_tools.py`
- Modify: `hermes_cli/config.py`
- Modify: `cli-config.yaml.example`

- [ ] **Step 1: Add the config defaults**

```python
"stt": {
    "enabled": True,
    "provider": "local",
    "local": {"model": "base", "language": ""},
    "parakeet": {"base_url": ""},
    "openai": {"model": "whisper-1"},
    "mistral": {"model": "voxtral-mini-latest"},
},
```

- [ ] **Step 2: Add the Parakeet provider selector and backend check**

```python
def _has_parakeet_backend(stt_config: dict) -> bool:
    parakeet_cfg = stt_config.get("parakeet", {})
    return bool((parakeet_cfg.get("base_url") or "").strip())


if provider == "parakeet":
    if _has_parakeet_backend(stt_config):
        return "parakeet"
    logger.warning("STT provider 'parakeet' configured but base_url is missing")
    return "none"
```

- [ ] **Step 3: Add the minimal HTTP transcription function**

```python
def _transcribe_parakeet(file_path: str, model_name: str) -> Dict[str, Any]:
    stt_config = _load_stt_config()
    base_url = stt_config.get("parakeet", {}).get("base_url", "").rstrip("/")
    if not base_url:
        return {"success": False, "transcript": "", "error": "Parakeet STT base_url is not configured"}

    try:
        with open(file_path, "rb") as audio_file:
            response = httpx.post(
                f"{base_url}/transcribe",
                files={"file": (Path(file_path).name, audio_file, "application/octet-stream")},
                timeout=120,
            )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return {"success": False, "transcript": "", "error": f"Parakeet transcription failed: {type(exc).__name__}"}

    transcript = str(payload.get("text", "")).strip()
    if not transcript:
        return {"success": False, "transcript": "", "error": "Parakeet returned an empty transcript"}
    return {"success": True, "transcript": transcript, "provider": "parakeet"}
```

- [ ] **Step 4: Wire dispatch into `transcribe_audio(...)`**

```python
if provider == "parakeet":
    return _transcribe_parakeet(file_path, model or "")
```

- [ ] **Step 5: Run the same test set and confirm it passes**

Run:

```bash
source .venv/bin/activate && pytest \
  tests/tools/test_transcription_tools.py \
  tests/hermes_cli/test_totoro_deploy_config.py \
  tests/integration/test_totoro_parakeet_stt_contract.py \
  tests/e2e/test_totoro_parakeet_stt_contract.py -q
```

Expected: all tests pass with pristine output.

### Task 3: Point Dee at Parakeet and document it

**Files:**
- Modify: `deploy/config-dee.yaml`
- Modify: `deploy/totoro_docker_install.md`

- [ ] **Step 1: Update Dee's config seed**

```yaml
stt:
  provider: "parakeet"
  parakeet:
    base_url: "http://172.17.0.1:8770"
```

- [ ] **Step 2: Update the Totoro deployment doc**

```markdown
`hermes-dee` uses Totoro's host `parakeet-stt` service for inbound voice transcription:

- host service: `http://127.0.0.1:8770`
- container bridge target: `http://172.17.0.1:8770`
```

- [ ] **Step 3: Run the targeted contract tests again**

Run:

```bash
source .venv/bin/activate && pytest \
  tests/hermes_cli/test_totoro_deploy_config.py \
  tests/integration/test_totoro_parakeet_stt_contract.py \
  tests/e2e/test_totoro_parakeet_stt_contract.py -q
```

Expected: all contract tests pass with no warnings.

### Task 4: Verify locally, then wire Totoro live

**Files:**
- Modify: `deploy/config-dee.yaml`
- Modify: `deploy/totoro_docker_install.md`

- [ ] **Step 1: Run the full targeted verification set**

Run:

```bash
source .venv/bin/activate && pytest \
  tests/tools/test_transcription_tools.py \
  tests/gateway/test_stt_config.py \
  tests/hermes_cli/test_totoro_deploy_config.py \
  tests/integration/test_totoro_parakeet_stt_contract.py \
  tests/e2e/test_totoro_parakeet_stt_contract.py -q
```

Expected: all selected tests pass with pristine output.

- [ ] **Step 2: Deploy the Dee config to Totoro and restart the service**

Run:

```bash
rsync -av deploy/config-dee.yaml deploy/totoro_docker_install.md totoro_ts:/tank/services/active_services/hermes/deploy/
ssh totoro_ts 'cd /tank/services/active_services/hermes/deploy && sudo systemctl restart hermes-dee.service'
```

Expected: `hermes-dee.service` restarts successfully.

- [ ] **Step 3: Verify Dee resolves Parakeet inside the live container**

Run:

```bash
ssh totoro_ts 'sudo docker exec hermes-dee python -c "from tools.transcription_tools import _load_stt_config,_get_provider; cfg=_load_stt_config(); print(cfg); print(_get_provider(cfg))"'
```

Expected: config shows `provider: parakeet` and the final printed provider is `parakeet`.

- [ ] **Step 4: Verify Dee can reach the host STT endpoint from inside the container**

Run:

```bash
ssh totoro_ts 'sudo docker exec hermes-dee python -c "import urllib.request; r=urllib.request.urlopen(\"http://172.17.0.1:8770/health\", timeout=5); print(r.status); print(r.read(200).decode())"'
```

Expected: `200` and a healthy Parakeet JSON body.

- [ ] **Step 5: Verify the service state**

Run:

```bash
ssh totoro_ts 'sudo systemctl is-active hermes-dee.service && sudo systemctl is-active parakeet-stt.service'
```

Expected: both services print `active`.
