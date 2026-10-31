---
name: platform-deployment
description: Deploy ResolveX AI to DigitalOcean using private networking, secrets, containers, managed services, and GPU inference.
---
# Platform Deployment
- Use App Platform for frontend/API/worker containers where suitable.
- Use Managed PostgreSQL and Valkey only after verifying extension and version requirements.
- Use a self-managed PostgreSQL/Apache AGE service if the managed database does not support AGE.
- Use private Spaces buckets and short-lived upload/download URLs.
- Host Gemma 4 on a GPU Droplet or tested custom inference endpoint; verify exact model/runtime modality support first.
- Do not assume Gemma 4 is in DigitalOcean's serverless model catalogue.
- Keep all keys in secret environment configuration, never in source or client bundles.
- Add health checks, logs, metrics, backups, TLS, firewall rules, and a deployment rollback path.
