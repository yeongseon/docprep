---
title: Changelog
---

# Changelog

All notable changes to the Acme SDK.

## v2.1.0 — 2024-11-15

### Added
- Batch processing endpoint for bulk operations
- Vision model support for image understanding
- Rate limit headers in all responses

### Changed
- Default timeout increased from 15s to 30s
- Retry logic now uses exponential backoff

### Fixed
- Connection pool exhaustion under high concurrency
- Token refresh race condition

## v2.0.0 — 2024-09-01

### Breaking Changes
- Authentication tokens are now required for all endpoints
- Batch responses include a `job_id` field for async tracking
- Rate limit headers use `X-RateLimit-*` prefix (was `RateLimit-*`)

### Added
- Async client support via `AsyncClient`
- Configurable retry policies
- Request/response logging middleware

## v1.3.0 — 2024-06-15

### Added
- Rate limiting headers
- Request ID tracking
- Improved error messages with actionable suggestions
