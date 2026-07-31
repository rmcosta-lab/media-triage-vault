# Mission

## What we are building

Local Media Organizer is a desktop/local application that analyzes a folder of photos and videos, extracts metadata, classifies each file along multiple dimensions, presents the results for review, and — only after explicit user confirmation — moves files into user-defined destination folders.

Source of truth for detailed requirements: [README_media_triage_vault.md](../README_media_triage_vault.md).

## Core principles (the constitution)

These are non-negotiable across all phases:

1. **100% local and offline.** No files, metadata, coordinates, thumbnails, or results ever leave the machine. No external APIs, no telemetry, no analytics, no CDN assets, no online geocoding. The backend listens on `127.0.0.1` only.
2. **Nothing moves without explicit confirmation.** Analysis is strictly read-only. A full dry-run move plan is generated and validated before any file operation, and execution requires an explicit approval step.
3. **Never destroy data.** Never overwrite silently (default collision policy: `error`). Never delete a source before the destination copy is validated (size/SHA-256 per validation mode). Every move is recorded in a transactional journal, execution is idempotent, and interrupted runs are resumable.
4. **Explainable classification.** Every automatic classification carries a confidence score (0.00–1.00) and a list of human-readable reasons. Low-confidence results are flagged for review, and manual overrides are recorded separately from automatic results (`automatic_` / `manual_` / `effective_routing_group`).
5. **Multidimensional classification.** A file is described by independent dimensions — `media_kind`, `source_origin`, `image_format`, `capture_country_code`, `routing_group` — so no information is lost when a file matches more than one characteristic. Routing follows a defined priority: `video > mobile_screenshot > whatsapp_received > iphone_raw > iphone_photo > other`.
6. **Deterministic rules first, AI later.** The MVP classifies using file type, name, path, EXIF/XMP/QuickTime metadata, dimensions, and scored deterministic rules. Local AI (embeddings, VLM enrichment on the RTX 4090) is a future phase and never a MVP dependency.
7. **Core before interface.** Build and validate the Python engine and CLI first, then expose it via a local FastAPI, then add the Next.js UI, and only package with Tauri after the flow is validated.

## Target user and environment

- A single user organizing a large personal photo/video collection (50,000+ files) on **Windows 11**, primary hardware target with future NVIDIA RTX 4090 for the AI phase.
- **macOS is a best-effort secondary target**: the core is written without OS-specific assumptions (see tech-stack "Cross-platform"), but only Windows is tested and released for the MVP. macOS validation is a post-MVP item.
- Typical sources: iPhone camera rolls (including ProRAW DNG), WhatsApp media, mobile screenshots, other cameras, and miscellaneous files.

## MVP definition of done

The MVP is complete when the system can, end to end: scan a folder recursively; identify media types by real content (not just extension); classify iPhone / iPhone RAW / WhatsApp / screenshot with documented rules and confidence; resolve capture country from GPS fully offline; produce local HTML/JSON/CSV reports; support review and manual overrides; let the user map routing groups to destination folders; generate and validate a dry-run move plan; execute moves through the transactional journal without overwriting; validate every moved file; and resume an interrupted run. Full acceptance list: README §31.

## Out of scope (MVP)

Cloud upload, external APIs, online geocoding, face/person recognition, semantic content classification, automatic album generation, editing original metadata, permanent deletion, auto-dedup with removal, continuous folder watching, mobile app, distributed processing, model training/fine-tuning.
