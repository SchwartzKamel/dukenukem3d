---
name: "Key Rotation Checklist"
description: "Track Azure API key rotation and credential updates"
labels: ["security", "maintenance"]
---

## Key Rotation Tracking

**Rotation Date**: [Date]  
**Keys Rotated**:
- [ ] `AUDIO_API_KEY` — Azure OpenAI Audio/TTS
- [ ] `FLUX_API_KEY` — Azure FLUX image generation
- [ ] Endpoint URLs (if applicable)

## Pre-Rotation

- [ ] Verified current API keys are functional
- [ ] Backup of old key values stored securely (for rollback if needed)
- [ ] Notified team of planned rotation window

## Rotation Steps

- [ ] Logged into Azure portal with appropriate credentials
- [ ] Located correct resource (Cognitive Services)
- [ ] Initiated key regeneration
- [ ] Captured new key values
- [ ] Updated local `.env` file with new keys
- [ ] Verified `.env` is NOT staged for commit
- [ ] Updated GitHub repository secrets (Settings > Secrets and variables > Actions)

## Post-Rotation Validation

- [ ] CI smoke test pipeline executed successfully
- [ ] Asset generation pipeline tested with new keys (if applicable)
- [ ] TTS/FLUX API calls verified working
- [ ] No stale keys remain in logs or error messages
- [ ] Old keys revoked in Azure portal

## Documentation

- [ ] Rotation date and scope documented in this ticket
- [ ] Team notified of successful rotation
- [ ] Audit trail preserved (link to this ticket in commits/comments)

## Next Rotation

**Scheduled For**: [90 days from rotation date]  
**Reminder Set**: [ ] Yes

**Notes**:
<!-- Add any additional context or blockers here -->
