# Twitter MCP Contract

This document locks the stable `twitter_source` MCP contract used by manifests and chains.

## Endpoint

- Public API route: `/api/v1/mcp/twitter`
- Transport: HTTP JSON-RPC
- Methods: `tools/list`, `tools/call`

## Tools

### `fetch_x_profile_timeline`

- **Arguments**
  - `handle` (string, required)
  - `limit` (integer, optional, default `10`, clamp `1..50`)
- **Result payload**
  - `source` (string)
  - `handle` (string, starts with `@`)
  - `count` (integer)
  - `posts` (array)

### `fetch_x_post`

- **Arguments**
  - `url_or_id` (string, required)
- **Result payload**
  - `source` (string)
  - `post` (object)

### `search_x_posts`

- **Arguments**
  - `query` (string, required)
  - `limit` (integer, optional, default `10`, clamp `1..50`)
- **Result payload**
  - `source` (string)
  - `query` (string)
  - `count` (integer)
  - `posts` (array)

### `check_x_sessions`

- **Arguments**
  - none
- **Result payload**
  - `accounts` (array with `username`, `logged_in`, `in_cooldown`, `failures`)
  - `count` (integer)

## Post Object Schema

- `id` (string)
- `author_handle` (string)
- `text` (string)
- `url` (string)

## Error Semantics

- JSON-RPC transport always returns HTTP 200 for tool errors.
- Tool errors are returned as content text payload:
  - `{"error":"...message..."}`
- API proxy prefixes transport-level errors with `Twitter source error:`.

## Compatibility Rule

Do not rename tools or remove fields above without updating:

- `example-manifests/x-trend-scout-manifest.json`
- `example-manifests/x-personality-builder-manifest.json`
- any marketplace chain relying on `twitter_source`.
