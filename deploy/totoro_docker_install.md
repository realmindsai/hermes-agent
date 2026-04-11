# Totoro Docker Install

This page is now just a routing note. The Hermes gateway and the nutrition service have separate source-of-truth runbooks.

## Hermes Gateway

Use:

- `deploy/totoro_hermes_gateway.md`

That runbook owns:

- Dee and Tracy runtime setup
- gateway secrets
- Docker and systemd details for Hermes
- Parakeet wiring for Dee
- the Dee-only Obsidian mount

## Nutrition Service

Use the standalone nutrition repo:

- `/Users/dewoller/code/personal/nutrition/deploy/totoro_nutrition_service.md`

That runbook owns:

- the nutrition-service runtime
- the nutrition Postgres database and role
- nutrition dataset imports
- the standalone nutrition API

## API Contract

Use the standalone nutrition repo:

- `/Users/dewoller/code/personal/nutrition/docs/api/nutrition_service_v1.md`
- `/Users/dewoller/code/personal/nutrition/openapi/nutrition_service_v1.yaml`

Hermes is a client of that API. Hermes is not the owner of nutrition storage or nutrition service operations.
