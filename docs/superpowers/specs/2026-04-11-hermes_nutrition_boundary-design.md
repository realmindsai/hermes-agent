# Hermes Nutrition Boundary Design

## Goal

Separate Hermes gateway concerns from nutrition-service concerns so the nutrition bot can operate as a standalone service with a stable versioned API, while Hermes remains only one client that happens to be good at getting Telegram meal photos into the system.

This design should make three things explicit:

- Hermes is a client of nutrition-service, not a co-owner of nutrition state.
- nutrition-service owns behavior and storage behind a versioned HTTP contract.
- operator documentation for Hermes and nutrition-service must be separate.

## Current State

The current branch has moved useful behavior into `nutrition_service/`, but the runtime and documentation boundaries are still muddy:

- the nutrition service has its own FastAPI app, CLI, Postgres settings, and Totoro runtime artifacts
- Hermes currently talks to the service through `nutrition_service/client.py`
- the public-ish request shape still reflects Hermes-local assumptions such as local image-path handoff
- Totoro deployment notes currently mix Hermes gateway runtime, nutrition-service runtime, and the interface between them into one blended install story

That is enough to build on, but it is not yet a clean service boundary.

## Problem

If Hermes and nutrition-service stay tightly coupled, the repo drifts toward the wrong abstraction:

- Hermes docs become pseudo-nutrition docs
- nutrition-service becomes “the thing Hermes uses” instead of a standalone system
- future clients would need to read Hermes code or nutrition database internals to integrate safely
- local implementation shortcuts such as filesystem `image_paths` start hardening into accidental public contracts

The real boundary should be behavior, not tables and not local runtime details.

## Requirements

### Architectural

- nutrition-service must be documented and operated as a standalone service
- Hermes must be documented as a client of nutrition-service, not as the owner of nutrition logic
- the service boundary must be a versioned API, not a shared database contract
- nutrition-service must keep its Postgres schema private

### Interface

- the public contract must live at `/api/nutrition/v1/...`
- v1 must be synchronous request/response
- `POST /analyze` must accept image uploads through a standalone contract, not Hermes-local filesystem paths
- `POST /select` and `POST /correct` must accept JSON
- responses must use opaque IDs and client-safe fields only

### Documentation

- Hermes operator documentation must be separate from nutrition-service operator documentation
- the versioned API contract must be documented separately from both deploy runbooks
- the machine-readable OpenAPI spec must live with nutrition-service
- the old blended Totoro doc must stop being the source of truth

### Client Boundary

Hermes may depend on:

- `NUTRITION_SERVICE_BASE_URL`
- versioned API endpoints and schemas
- opaque `candidate_set_id`, `candidate_id`, and `meal_log_id`
- documented service error/status semantics

Hermes may not depend on:

- nutrition-service Postgres tables
- nutrition-service dataset import layout
- nutrition-service ranking internals
- nutrition-service correction/default storage internals
- nutrition-service runtime file layout beyond the documented HTTP base URL

## Chosen Approach

Use a standalone versioned HTTP API backed by a private Postgres database. Split documentation into service-owned runbooks plus a separate API contract.

### Why Not A Shared Database

A shared database is the wrong boundary for this system because clients are not merely reading rows. They need service behavior:

- analyze meal images
- generate ranked candidates
- apply source precedence
- accept corrections
- learn defaults
- log final meals

If multiple clients talk directly to the nutrition database, either they duplicate service logic or they become tightly coupled to nutrition internals. Both outcomes are worse than a clean API.

### Why A Versioned API

A versioned API gives future clients one stable integration target:

- Hermes can integrate without understanding nutrition internals
- other services can call the same contract later
- the service can refactor internals and keep the same external behavior
- contract tests can target the public boundary directly

## Documentation Split

The current blended deployment note should be replaced by three authoritative documents plus one lightweight index.

### 1. Hermes Gateway Runbook

Path:

- `deploy/totoro_hermes_gateway.md`

Owns:

- Dee and Tracy runtime setup
- Hermes secrets and login steps
- messaging platform setup
- Hermes-specific verification
- `NUTRITION_SERVICE_BASE_URL`
- the fact that Hermes forwards meal-analysis requests to nutrition-service

Does not own:

- nutrition-service Postgres bootstrap
- nutrition-service dataset imports
- nutrition-service API semantics beyond linking to the interface doc

### 2. Nutrition-Service Runbook

Path:

- `deploy/totoro_nutrition_service.md`

Owns:

- `hermes-nutrition.service`
- `/tank/services/active_services/hermes-nutrition-service`
- `/run/secrets/hermes-nutrition-service/.env`
- database bootstrap
- migrations
- dataset imports
- service logs
- nutrition-service verification

Does not assume Hermes exists. Hermes may be mentioned as one possible client, but not as a prerequisite for understanding or operating the service.

### 3. Human-Readable API Contract

Path:

- `docs/api/nutrition_service_v1.md`

Owns:

- endpoint list
- request/response schemas
- status codes
- idempotency expectations
- error semantics
- client responsibilities versus service responsibilities

This is the contract humans read first.

### 4. Machine-Readable API Contract

Path:

- `nutrition_service/openapi.yaml`

Owns:

- the machine-readable version of the same API contract
- canonical endpoint schemas for client generation and contract validation

This is the contract machines and tests read first.

### 5. Totoro Index Page

Path:

- `deploy/totoro_docker_install.md`

This file should stop being the source of truth. Its role should be reduced to one of:

- a short routing page that links to the Hermes gateway runbook and the nutrition-service runbook, or
- a retired/archived compatibility page replaced by the two new runbooks

The recommendation is to keep it as a short routing page to avoid breaking existing links immediately.

## API Boundary

The service boundary is a synchronous versioned HTTP API rooted at `/api/nutrition/v1`.

### Endpoints

- `GET /api/nutrition/v1/health`
- `POST /api/nutrition/v1/analyze`
- `POST /api/nutrition/v1/select`
- `POST /api/nutrition/v1/correct`

### `POST /analyze`

V1 should use `multipart/form-data` rather than Hermes-local file paths.

Form shape:

- one metadata part containing JSON
- one or more image file parts

Metadata fields:

- `client`
- `client_request_id` optional idempotency key
- `session_ref` opaque client session reference
- `caption_text` optional caption

This keeps the public contract standalone. Hermes can upload Telegram photo bytes. Another service could upload files from a web form. Neither needs shared filesystem assumptions.

### `POST /select`

JSON request:

- `candidate_set_id`
- `candidate_id`
- `client_request_id` optional

JSON response:

- `logged`
- `meal_log_id`
- `message`

### `POST /correct`

JSON request:

- `candidate_set_id`
- `correction_text`
- `client_request_id` optional

JSON response:

- `logged`
- `meal_log_id`
- `message`

### Public Response Rules

Responses may include:

- opaque IDs
- user-visible nutrient summaries
- confidence and explanation text
- service-safe error messages

Responses must not include:

- internal table identifiers
- source-table implementation details
- Telegram-specific state
- filesystem paths

## Service Responsibilities

nutrition-service owns:

- image analysis
- candidate generation
- source precedence
- correction handling
- adaptive learning
- meal logging
- private Postgres schema

Hermes owns:

- receiving Telegram messages
- downloading Telegram media
- sending uploaded bytes to the service
- rendering ranked candidates to the user
- sending selection/correction requests back to the service

## Private Storage Boundary

The nutrition-service database remains private.

Private schema includes:

- source import tables
- normalized nutrient profiles
- OCR observations
- candidate persistence
- correction history
- learned defaults
- meal logs

Clients must not read or write these tables directly.

If future reporting or analytics needs direct database access, expose that separately through:

- read-only views, or
- an explicit reporting surface

That is not part of the v1 client boundary.

## Migration From Current Internal Shape

The current internal service flow still uses Hermes-local `image_paths`. That is acceptable as a temporary implementation detail, but it must not remain the documented public contract.

### Migration Plan

1. Introduce the standalone multipart `/api/nutrition/v1/analyze` contract in docs and OpenAPI.
2. Update Hermes to upload image bytes instead of passing local paths.
3. Keep any path-based internal adapter private during transition if needed.
4. Remove path-based assumptions from public-facing docs and public client helpers.

The important rule is simple: the docs define the target boundary, not the current shortcut.

## Testing Strategy

### Contract Tests

- validate OpenAPI structure for `/api/nutrition/v1`
- validate human-readable docs and OpenAPI stay in sync on endpoints and field names
- validate Hermes integration against the public contract, not nutrition internals

### Hermes Tests

- Hermes tests should assert it uses `NUTRITION_SERVICE_BASE_URL`
- Hermes tests should cover multipart upload behavior and select/correct requests
- Hermes tests should not inspect nutrition-service database state directly

### Nutrition-Service Tests

- nutrition-service tests should validate endpoint schemas and response behavior
- service tests should validate internal DB behavior separately behind the API boundary

### Docs Tests

- deploy docs should be validated separately:
  - Hermes runbook checks
  - nutrition-service runbook checks
  - API contract checks

## Non-Goals

- No repo split
- No async job model in v1
- No shared DB contract for clients
- No Telegram-specific callback formats in the public nutrition-service API docs
- No analytics/reporting API in this phase

## Acceptance Criteria

- Hermes gateway documentation is separated from nutrition-service runtime documentation.
- The nutrition-service API is documented as a standalone versioned contract.
- The public contract defines multipart image upload for `POST /analyze` rather than filesystem `image_paths`.
- nutrition-service is documented as deployable and operable without assuming Hermes.
- Hermes is documented strictly as one client of the service.
- The old Totoro doc is reduced to an index or retired as a source of truth.
