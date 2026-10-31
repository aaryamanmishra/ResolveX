---
name: multimodal-evidence
description: Implement secure image, PDF, and audio intake with Gemma/Gemini extraction, source provenance, consent, and user confirmation.
---
# Multimodal Evidence
- Validate type, size, tenant ownership, malware scan, and storage policy before model processing.
- Keep evidence objects private and use short-lived signed URLs.
- Keep extracted fields as candidate claims with confidence and source location.
- User confirmation is required for uncertain or conflicting values.
- Never use OCR/model extraction to overwrite payment-provider state.
- Route to Gemini only when tenant policy and explicit consent allow it; redact unnecessary identifiers.
- Do not load user-uploaded instructions/skills as trusted prompts.
