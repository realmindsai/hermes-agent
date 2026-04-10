# Telegram Nutrition Bot Design

## Goal

Build a dedicated private Telegram nutrition bot that accepts meal photos in a direct message, estimates calories and nutrient composition, asks the user to choose from `2-3` candidates when confidence is not decisive, accepts both button and free-text corrections, and replies in text only.

The bot should get smarter from correction history and personal defaults without mutating canonical nutrition facts. Hermes should remain the Telegram front end. A separate nutrition service should own nutrition truth, adaptive ranking, and the meal log.

## Scope

This design covers:

- a dedicated Telegram bot and Hermes profile for nutrition logging
- DM photo intake only
- packaged foods plus plated meals
- a separate nutrition service backed by Postgres
- branded-food recognition and generic-food nutrient lookup from external datasets
- candidate selection, correction handling, and adaptive ranking

This design does not cover:

- Telegram channel-post support
- group-chat workflows
- voice replies or audio output
- direct write-through into Garmin or another health system
- barcode-first scanning as a separate mode

## Current State

Hermes already has useful seams for this feature:

- [`gateway/platforms/telegram.py`](/Users/dewoller/code/personal/hermes-agent/gateway/platforms/telegram.py) already receives Telegram photos, caches them locally, and supports inline callback buttons.
- [`gateway/run.py`](/Users/dewoller/code/personal/hermes-agent/gateway/run.py) already enriches inbound image messages through the vision path before the agent responds.

Those seams make Hermes a good Telegram shell for this feature, but not a good home for nutrition state.

There is also one Telegram constraint worth making explicit: the current adapter handles normal message updates cleanly, but this v1 should use a direct bot chat rather than a private channel. That keeps the product aligned with the existing adapter path instead of adding channel-post support before the core nutrition loop exists.

The previously discussed `shopping_bot` or `shopping_deal_spotter` data is not load-bearing for this design. It is useful for shopping and product-name context, but it does not provide the calorie, macro, serving-size, or provenance model needed for a nutrition bot. V1 should not depend on it.

## Recommended Architecture

Use a dedicated Telegram bot and dedicated Hermes profile as the chat front end. Put all nutrition state and decision-making behind a separate nutrition service with Postgres.

### Components

#### Hermes Nutrition Bot

Hermes is responsible for:

- receiving DM photos and captions
- caching uploaded images
- forwarding image-analysis requests to the nutrition service
- presenting ranked candidates in Telegram
- accepting inline-button picks and free-text corrections
- replying with short logged summaries in text

Hermes is not responsible for:

- owning canonical food data
- calculating nutrition truth directly
- storing meal history as primary state
- learning nutrition facts from user corrections

That boundary keeps the bot simple and keeps nutrition logic out of the gateway code.

#### Nutrition Service

The nutrition service is the authority for:

- branded product lookup
- generic food lookup
- candidate generation for packaged and plated meals
- confidence scoring
- correction handling
- adaptive ranking
- meal logging
- audit history

The service exposes a small API that Hermes can call. Hermes should not read the imported nutrition tables directly.

#### Postgres

Postgres stores:

- raw source records from branded and generic food datasets
- normalized food identity and nutrient profiles
- OCR and label observations
- meal logs and meal candidates
- correction events and learned user defaults

The database should preserve both nutrition facts and interaction history. That separation matters. Nutrition facts are canonical data. Adaptive behavior comes from ranking and defaults, not from rewriting the source nutrition facts because the user corrected one meal.

## Source Strategy

V1 should separate `recognition` from `nutrition truth`.

- `recognition sources` answer what product or food the image likely shows
- `nutrition sources` answer which nutrient values should be used for the resolved item and serving
- `user-confirmed observations` outrank both once the user has corrected the bot

### Packaged-Food Sources

For packaged foods, the service should resolve in this order:

1. actual label and nutrition-panel OCR from the current image
2. prior user-confirmed matches and snapshots
3. Open Food Facts for branded identity and structured nutriment fields
4. USDA branded foods as a fallback
5. generic fallback only when forced

### Plated-Meal Sources

For plated meals, the service should resolve in this order:

1. prior user corrections and personal defaults
2. FSANZ AFCD as the primary Australian generic-food nutrient source
3. USDA generic foods as a fallback
4. derived component-level estimates when no direct match exists

### What V1 Should Not Depend On

V1 should not depend on:

- `shopping_deal_spotter`
- live retailer price data
- shopping catalog feeds
- private Telegram channels

Those things may be useful later, but they do not solve the nutrient-truth problem.

### Licensing Boundary

Raw source tables must remain separate. The nutrition service should not build one merged raw source table that copies Open Food Facts, FSANZ, and USDA data into a single undifferentiated store.

Instead, the service should:

- keep source-specific raw tables
- create app-level normalized entities that point back to source rows
- store the nutrient snapshot actually used for each meal event
- preserve provenance for every nutrient profile

This avoids mixing source licenses into one opaque database and makes audit and debugging straightforward.

## Data Model

V1 needs an explicit model with three layers: raw sources, app identity, and meal interactions.

### Raw Source Tables

- `source_product_off`
  Stores Open Food Facts branded-product records, including barcode, product name, brand, quantity text, serving text, image URLs, nutriments JSON, and raw payload.
- `source_food_fsanz`
  Stores FSANZ generic-food records and source metadata.
- `source_food_fsanz_nutrient`
  Stores FSANZ nutrient rows keyed to `source_food_fsanz`.
- `source_food_usda`
  Stores USDA generic and branded-food records and source metadata.
- `source_food_usda_nutrient`
  Stores USDA nutrient rows keyed to `source_food_usda`.

### App Identity Tables

- `food_item`
  Stores the app-level food identity used by the bot. `kind` should distinguish `packaged`, `generic`, and `meal`.
- `food_item_alias`
  Stores aliases, barcode mappings, user labels, and normalized recognition text.
- `food_item_source_link`
  Stores links from a `food_item` to one or more source rows with source role and confidence.

### Nutrient And Evidence Tables

- `nutrient_profile`
  Stores the normalized nutrient vector actually used by the app. `profile_kind` should distinguish `source_import`, `label_observation`, `user_confirmed`, and `derived_recipe`.
- `image_asset`
  Stores Telegram image references and cached storage paths.
- `label_observation`
  Stores OCR output from an actual product image, including parsed barcode, product text, serving text, parsed nutrient rows, confidence, and review status.

### Meal And Learning Tables

- `analysis_request`
  Stores one incoming analysis job per DM event.
- `analysis_request_image`
  Stores the ordered images attached to that request.
- `meal_candidate_set`
  Stores the candidate batch shown to the user.
- `meal_candidate`
  Stores each ranked option, including macros, confidence, serving estimate, and explanation text.
- `meal_log`
  Stores the final accepted meal event, including the nutrient profile used and the source path.
- `correction_event`
  Stores what the bot proposed, what the user selected or typed, and how the final result was resolved.
- `user_food_default`
  Stores recurring servings and confirmed defaults for known foods.
- `user_alias`
  Stores short user-specific names for recurring foods and meals.

## Request Flow

1. The user sends one or more meal photos to the nutrition bot in a direct message, optionally with a caption.
2. Hermes stores the image references in `image_asset`, creates an `analysis_request`, and forwards the request to the nutrition service.
3. The nutrition service runs two interpretation paths in parallel:
   - `packaged-food path`: detect wrapper text, barcode, brand, product name, and possible nutrition-panel content
   - `plated-meal path`: detect meal components, portion cues, and recurring-meal hints
4. If a label or nutrition panel is visible, the service creates a `label_observation`. That observation is evidence, not truth yet.
5. The service resolves likely `food_item` matches:
   - barcode exact match first
   - then brand and product-name fuzzy match
   - then user alias and correction history
   - then broader source-backed candidates
6. The service selects a nutrient basis:
   - for packaged foods: confirmed label snapshot, current high-confidence label observation, existing user-confirmed profile, Open Food Facts, USDA branded fallback, then generic fallback
   - for plated meals: existing user-confirmed profile, FSANZ, USDA generic fallback, then derived component estimate
7. The service creates a `meal_candidate_set` with `2-3` ranked `meal_candidate` rows. Each candidate includes a title, serving estimate, calories, protein, carbs, fat, confidence, and a short reason line.
8. Hermes replies with inline buttons for the candidates and also accepts free-text correction.
9. If the user taps a button or types a correction, Hermes sends that context back to the nutrition service.
10. The nutrition service resolves the final meal log, stores a `correction_event`, updates learned defaults when appropriate, and returns the logged result.
11. Hermes replies with a short text confirmation.

## Candidate And Correction UX

V1 should optimize for fast logging without pretending uncertainty does not exist.

### Default Reply

The first reply after analysis should be compact:

- meal or product name
- calories
- protein
- carbs
- fat
- short confidence or explanation line

Micronutrients should appear only when the source is good enough or when the user explicitly asks for detail.

### Candidate Selection

For v1, the system should default to showing `2-3` candidates. Strong branded packaged-food matches may auto-log later, but that should not be the default v1 behavior. Plated meals should never silently auto-log in v1, even when the ranking is good.

Hermes should present `2-3` candidates using inline buttons. Each candidate should map to a stable candidate identifier from the nutrition service, not to fragile text parsing in Telegram.

### Free-Text Correction

Buttons cover the common path. Free-text corrections cover the edge cases. The free-text path should allow short corrections such as:

- `2 eggs and one slice of sourdough`
- `this was the Carman's chocolate protein bar`
- `same tuna salad as yesterday but double portion`

Hermes should pass that correction text to the nutrition service, which re-ranks or resolves the meal using the stored candidate context plus the correction text.

## Adaptive Learning Rules

The system should learn ranking behavior, not rewrite nutrition truth.

It should learn from:

- accepted candidates
- rejected candidates
- free-text corrections
- recurring meal names
- recurring brand choices
- typical portion choices
- useful aliases such as the user's shorthand for a known meal

It should not:

- silently edit canonical nutrition facts in source-backed nutrient profiles
- infer permanent facts from one ambiguous photo
- auto-log low-confidence meals without showing candidates

This is the core safety rule for the feature. The bot can learn what the user usually means. It must not learn new nutrition facts from vibes.

## Error Handling

Failures should degrade cleanly and visibly.

- If the image is unreadable, the bot should say so and ask for a clearer photo or a text description.
- If the nutrition service cannot ground a branded product well, it should return ranked candidates with explicit low-confidence wording.
- If the plated-meal estimate is weak, the bot should present its best candidates and invite correction rather than logging a guess as fact.
- If the service is unavailable, Hermes should return a short failure message and avoid partial logging.
- If the correction text is too ambiguous to resolve, the service should return a narrower follow-up prompt instead of pretending it understood.

## Testing

V1 needs all three test layers.

### Unit

- source importer normalization for Open Food Facts, FSANZ, and USDA
- candidate ranking rules
- confidence thresholds
- correction parsing
- adaptive-learning updates
- nutrient-profile precedence rules
- response formatting

### Integration

- Hermes DM photo intake to nutrition-service analysis request
- inline-button candidate selection round trip
- free-text correction round trip
- Postgres persistence for source records, nutrient profiles, meal logs, candidate sets, and corrections
- OCR observation promotion into confirmed nutrient profiles

### E2E

- real Telegram DM to the dedicated nutrition bot
- real image upload
- candidate response in text with buttons
- successful button choice
- successful free-text correction
- final meal log persistence and audit trail

## Operations

Run the system as two deployable units:

- `Hermes nutrition bot`
- `nutrition service`

The Hermes bot should use its own Telegram token and its own Hermes profile. It should have a narrow toolset. This bot should behave like a food clerk, not a general-purpose agent with a caffeine problem.

The nutrition service should own Postgres migrations, importer runs, and audit queries. Hermes should call it over HTTP. That boundary is simpler to secure, test, and evolve than direct database access from the gateway.

## Rollout

V1 rollout should be staged:

1. Build the nutrition service with Postgres and importer support for Open Food Facts, FSANZ, and USDA.
2. Stand up the dedicated Telegram nutrition bot profile in Hermes.
3. Wire the DM photo analysis and candidate-selection loop.
4. Add OCR-backed `label_observation` support for packaged foods.
5. Add correction handling and adaptive ranking.
6. Run end-to-end tests with real Telegram messages and representative meal photos.
7. Seed the database with the initial external datasets before normal use.

This rollout keeps the riskiest parts separate: data import, image interpretation, and Telegram UX.
