# Telegram Parakeet STT Design

## Goal

Make `hermes-dee` transcribe inbound Telegram voice and audio messages through Totoro's host `parakeet-stt` service, feed the transcript into the normal gateway flow, and keep reply behavior unchanged. Dee should answer in text unless some separate TTS path is already enabled.

## Scope

This design changes only Dee's Totoro deployment and the shared STT provider code needed to support a Parakeet backend. It does not change Tracy's deployment, the generic default STT provider order, or Telegram media classification.

## Current State

Telegram media handling already works:

- [`gateway/platforms/telegram.py`](/Users/dewoller/code/personal/hermes-agent/gateway/platforms/telegram.py) caches inbound `voice` and `audio` files to local paths.
- [`gateway/run.py`](/Users/dewoller/code/personal/hermes-agent/gateway/run.py) already calls `_enrich_message_with_transcription(...)` for `MessageType.VOICE` and `MessageType.AUDIO`.
- [`tools/transcription_tools.py`](/Users/dewoller/code/personal/hermes-agent/tools/transcription_tools.py) currently supports `local`, `local_command`, `groq`, `openai`, and `mistral`.

The live failure is configuration, not Telegram plumbing. Dee is configured for `stt.provider: local`, but the `hermes-dee` container does not have `faster_whisper` or a `whisper` CLI, so provider resolution returns `none`. Totoro now has a reachable host STT server at `http://172.17.0.1:8770`.

## Design

### STT Provider

Add an explicit `parakeet` provider to [`tools/transcription_tools.py`](/Users/dewoller/code/personal/hermes-agent/tools/transcription_tools.py).

The provider will:

- read `stt.parakeet.base_url` from config
- POST the cached audio file to `{base_url}/transcribe` as multipart form data
- accept Parakeet's JSON response and normalize `text` into the existing `{success, transcript, provider}` shape
- return a bounded, user-safe error string on network failures, HTTP failures, malformed JSON, or empty transcripts

Provider selection rules:

- `stt.provider: parakeet` must resolve only to `parakeet`
- explicit `parakeet` must not silently fall back to `openai`, `groq`, or any other provider
- auto-detect behavior for other users stays unchanged

### Dee Deploy Config

Update Dee's config seed in [`deploy/config-dee.yaml`](/Users/dewoller/code/personal/hermes-agent/deploy/config-dee.yaml):

- set `stt.provider: parakeet`
- set `stt.parakeet.base_url: http://172.17.0.1:8770`

This keeps the routing instance-specific. Tracy remains on the current default behavior.

### Config Defaults and Docs

Add `parakeet` to the STT config defaults and example config:

- [`hermes_cli/config.py`](/Users/dewoller/code/personal/hermes-agent/hermes_cli/config.py)
- [`cli-config.yaml.example`](/Users/dewoller/code/personal/hermes-agent/cli-config.yaml.example)

Update [`deploy/totoro_docker_install.md`](/Users/dewoller/code/personal/hermes-agent/deploy/totoro_docker_install.md) so the live Totoro install notes explain that Dee uses the host bridge at `172.17.0.1:8770` for STT.

## Data Flow

1. Telegram receives a voice note or audio file.
2. [`gateway/platforms/telegram.py`](/Users/dewoller/code/personal/hermes-agent/gateway/platforms/telegram.py) downloads it into the audio cache.
3. [`gateway/run.py`](/Users/dewoller/code/personal/hermes-agent/gateway/run.py) passes the cached path into `_enrich_message_with_transcription(...)`.
4. [`tools/transcription_tools.py`](/Users/dewoller/code/personal/hermes-agent/tools/transcription_tools.py) resolves `parakeet`, uploads the file to Totoro's host STT service, and returns transcript text.
5. The transcript is prepended to the user message, and the existing agent flow handles it normally.
6. Reply delivery remains unchanged.

## Error Handling

Failure should degrade cleanly:

- If Parakeet is unreachable, `_enrich_message_with_transcription(...)` should surface the existing "trouble transcribing" note, not crash message handling.
- If Parakeet returns a non-200 response or malformed JSON, the provider should return `success: false` with a short diagnostic string.
- If Parakeet returns an empty transcript, the provider should treat that as a transcription failure instead of pretending success.

## Testing

This change needs all three layers:

- Unit: provider resolution and Parakeet HTTP response handling in [`tests/tools/test_transcription_tools.py`](/Users/dewoller/code/personal/hermes-agent/tests/tools/test_transcription_tools.py)
- Integration: Dee deploy config contract in [`tests/integration/test_totoro_parakeet_stt_contract.py`](/Users/dewoller/code/personal/hermes-agent/tests/integration/test_totoro_parakeet_stt_contract.py)
- E2E: Totoro docs and/or Dee config seed contract in [`tests/e2e/test_totoro_parakeet_stt_contract.py`](/Users/dewoller/code/personal/hermes-agent/tests/e2e/test_totoro_parakeet_stt_contract.py)

## Live Verification

After repo tests pass, live verification on Totoro must prove:

- `parakeet-stt` is healthy on the host
- `hermes-dee` can reach `http://172.17.0.1:8770/health`
- inside `hermes-dee`, `tools.transcription_tools._get_provider(...)` resolves to `parakeet`
- `hermes-dee.service` restarts cleanly after the config change
