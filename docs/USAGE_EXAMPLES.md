# Usage and API Examples

**Language:** English | [中文](USAGE_EXAMPLES.zh-CN.md)

These examples use public-safe placeholder data. Replace URLs, tokens, paths, and settings before running them in your own environment, and make sure you are allowed to process the target data.

## Example 1: Health and status

Use health/status endpoints to verify configuration before starting media scans.

## Example 2: Dry-run sample scan

Keep `DRY_RUN=true`, run the sample job, then review generated reports before changing writeback settings.

## curl Examples

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/status
curl -X POST http://localhost:8080/api/jobs/run-sample
curl http://localhost:8080/api/reports
```

Request bodies can change between versions; use local `/docs` or the source model definitions as the final reference.


## Local Validation Tips

- Start from `README.md` and bring the service up first.
- Call the health endpoint before running operations that write state or send notifications.
- Use synthetic or public demo data; do not paste private data into issues, screenshots, or commits.
- When using an AI assistant, provide this file, the deployment guide, and sanitized logs.
