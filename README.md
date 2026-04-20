<div align="center">

# Ombre

**The infrastructure layer that makes AI trustworthy.**

Every AI system has three unsolved problems: it costs too much, it gets things wrong, and nobody can prove it behaved correctly. Ombre solves all three — running entirely inside your own infrastructure.

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL_1.1-blue.svg)](./LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)]()

**Your data never leaves your environment. You bring your own API keys.**

</div>

---

## What Ombre Does

Ombre sits between your application and any AI model. Every request flows through 8 agents automatically:

| Agent | What It Does |
|---|---|
| **Security** | Blocks prompt injection, redacts PII, stops harmful content |
| **Memory** | Persistent encrypted context across sessions |
| **Token** | Semantic cache + compression — 40–60% cost reduction |
| **Compute** | Routes to the best model and provider automatically |
| **Truth** | Pre-loads verified facts to reduce hallucinations |
| **Latency** | P99 monitoring, SLA enforcement, circuit breaking |
| **Reliability** | Validates output, scores confidence, catches hallucinations |
| **Audit** | Immutable tamper-proof log of every AI decision |

---

## Install

```bash
# Base install
pip install git+https://github.com/ombre-ai/ombre-core.git

# With your provider
pip install "git+https://github.com/ombre-ai/ombre-core.git#egg=ombre-ai[openai]"
pip install "git+https://github.com/ombre-ai/ombre-core.git#egg=ombre-ai[anthropic]"
pip install "git+https://github.com/ombre-ai/ombre-core.git#egg=ombre-ai[groq]"
pip install "git+https://github.com/ombre-ai/ombre-core.git#egg=ombre-ai[all-providers]"
```

**Air-gapped / offline environments:**
```bash
git clone https://github.com/ombre-ai/ombre-core.git
pip install ./ombre-core
```

---

## Quick Start

```python
from ombre import Ombre

ai = Ombre(
    openai_key="sk-...",        # Your key — Ombre never sees it
    # anthropic_key="sk-ant-...",
    # groq_key="gsk-...",
)

response = ai.run("Summarize our Q3 financials and recommend next steps")

print(response.text)                  # The answer
print(response.confidence)            # Verified confidence score (0.0–1.0)
print(response.cost_saved)            # Dollars saved vs raw API call
print(response.audit_id)              # Immutable audit reference
print(response.hallucinations_caught) # Bad answers stopped before reaching you
print(response.threats_blocked)       # Security events intercepted
```

---

## Multi-turn Chat

```python
response = ai.chat([
    {"role": "user", "content": "My name is Alex. I work in finance."},
    {"role": "assistant", "content": "Got it Alex, how can I help?"},
    {"role": "user", "content": "What should I focus on this quarter?"},
])
# Memory Agent remembers Alex works in finance — no need to repeat it
```

---

## Batch Processing

```python
responses = ai.batch([
    "Summarize contract 1",
    "Summarize contract 2",
    "Summarize contract 3",
], concurrency=5)
```

---

## Add Your Own Ground Truth

```python
# Verified facts — model uses these instead of guessing
ai.truth.add_fact(
    key="company_ceo",
    fact="The CEO of Acme Corp is Jane Smith, appointed January 2022",
    confidence=1.0,
    source="company_records",
)
```

---

## Audit Export

```python
# Export for compliance
ai.export_audit("audit.json", format="json")
ai.export_audit("audit.csv", format="csv")

# EU AI Act compliance report
ai.audit.generate_compliance_report(
    regulation="eu_ai_act",
    output_path="compliance_report.json",
)
```

---

## Self-Hosted REST API

Run a local server on your own infrastructure. Zero data leaves your environment.

```bash
# Start the server
python -m ombre serve --port 8080

# Or from CLI
ombre serve --port 8080
```

Call from any language:

```bash
# cURL
curl -X POST http://localhost:8080/v1/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your prompt here"}'
```

```python
# Python
import requests
r = requests.post("http://localhost:8080/v1/run",
    json={"prompt": "Your prompt here"})
print(r.json()["text"])
```

```javascript
// JavaScript / Node
const res = await fetch("http://localhost:8080/v1/run", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ prompt: "Your prompt here" })
})
const data = await res.json()
console.log(data.text)
```

```go
// Go
resp, _ := http.Post("http://localhost:8080/v1/run",
    "application/json",
    strings.NewReader(`{"prompt":"Your prompt here"}`))
```

---

## Environment Variables

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GROQ_API_KEY=gsk-...
export OMBRE_API_KEY=omb_ent_...   # Enterprise license key (optional)
```

Then initialize with no arguments:

```python
ai = Ombre()  # Reads keys from environment automatically
```

---

## Architecture

```
Your Application
      │
      ▼
┌─────────────────────────────────────┐
│           OMBRE LAYER               │
│  (runs inside your infrastructure)  │
│                                     │
│  1. Security Agent                  │
│  2. Memory Agent                    │
│  3. Token Agent  ◄── cache hit?     │
│  4. Compute Agent                   │
│  5. Truth Agent                     │
│  ── model inference ──              │
│  6. Latency Agent                   │
│  7. Reliability Agent               │
│  8. Audit Agent                     │
└─────────────────────────────────────┘
      │
      ▼
Your AI Model
(OpenAI / Anthropic / Groq / Mistral)
```

No Ombre server involved. Everything runs locally on your machine.

---

## Pricing

| Tier | Price | Who |
|---|---|---|
| **Free** | $0 forever | Developers, small startups |
| **Growth** | $2,500/month | Series A+ startups |
| **Enterprise** | Custom | Large companies |
| **Government** | Custom | Agencies, defense contractors |

Free tier includes all 8 agents with no time limit. No credit card required.

---

## Enterprise Licensing & Payment

Enterprise licenses are invoiced annually. Payment accepted in **USDT (TRC20) only**.

> ⚠️ **CRITICAL: Only send USDT on the TRC20 network.**
> Sending any other token or using ERC20 / BEP20 / any other network
> will result in **permanent loss of funds.**
> Ombre cannot recover misdirected payments.

**Network:** TRON (TRC20)  
**Token:** USDT only  
**Wallet address:** `TT3aCEYKF1d9PpyLDdzKGULi6Maa3DqPVU`  
**Memo:** Not required

### Step-by-step payment

1. Open your exchange or crypto wallet
2. Select **Send / Withdraw**
3. Select token: **USDT**
4. Select network: **TRC20** ← this is critical
5. Paste wallet address exactly: `TT3aCEYKF1d9PpyLDdzKGULi6Maa3DqPVU`
6. No memo required — leave blank
7. Send the exact invoice amount
8. Email the transaction hash to **ombreaiq@gmail.com**
   - Subject line: `Payment - [Your Company Name]`
   - Include: company name, license tier, transaction hash

License key delivered within 24 hours of confirmed payment on-chain.

---

## Contact

- **Email:** ombreaiq@gmail.com
- **GitHub:** [github.com/ombre-ai/ombre-core](https://github.com/ombre-ai/ombre-core)

---

## License

[Business Source License 1.1](./LICENSE) — Free for internal use. Converts to Apache 2.0 four years from each release date. Commercial hosting restrictions apply. See LICENSE for details.
