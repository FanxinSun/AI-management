---
name: poe-cli
description: Query Poe.com AI models and bots from the terminal, inspect compute points balance, list available models, and sync browser credentials. Use when asked to query models on Poe (e.g. Claude-Fable-5.1, Claude 3.5/4.5 Haiku/Sonnet, Gemini, Grok, GPT, or custom bots), check Poe account/points status for sunfxcatl@gmail.com, or test Poe connectivity.
---

# poe-cli: query Poe.com models and manage points from the terminal

Use `poe-cli` to query Poe bots, monitor compute points, and list model pricing.
Billed directly to `sunfxcatl@gmail.com`'s monthly compute points allotment (1.65 million points/month).

## Quick Verification

```bash
command -v poe-cli && poe-cli status
```

## Everyday Usage

```bash
# Check connection, live points balance, and API key
poe-cli status
poe-cli status --json

# Query the cheapest model (assistant — free / minimal points)
poe-cli chat "Hello from terminal"
poe-cli chat "Explain quantum entanglement in 10 words" --usage

# Stream responses in real time
poe-cli chat "Write a short poem" --stream

# Query specific models/bots
poe-cli chat "Analyze this diff" --model claude-haiku-4.5
poe-cli chat "Summarize findings" --model gemini-3.8-flash

# List available models and pricing
poe-cli models --cheapest --limit 15
poe-cli models --search claude
poe-cli models --search fable

# Sync browser credentials from running Windows Chrome (zero interruption)
poe-cli sync
```

## Agent Guidelines

- Never run interactive chat sessions in automated scripts. Always pass the prompt argument or pipe into stdin.
- Default to `--model assistant` or `--cheapest` models for testing/verification to conserve points.
- If credentials expire or report an auth error, run `poe-cli sync`.
