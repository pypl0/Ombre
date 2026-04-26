"""
Ombre + Mistral Integration
============================
Use Ombre as the security, caching, and audit layer
on top of your Mistral applications.

Install:
    pip install git+https://github.com/pypl0/Ombre.git
    pip install mistralai
"""

from ombre import Ombre

# Initialize with your Mistral key
ai = Ombre(mistral_key="your-mistral-key")

# Basic usage
response = ai.run(
    prompt="Write a Python function to sort a list",
    model="mistral-small",
)

print(f"Response: {response.text}")
print(f"Confidence: {response.confidence}")
print(f"Cost saved: ${response.cost_saved:.4f}")
print(f"Audit ID: {response.audit_id}")

# Use multiple providers with automatic fallback
ai_multi = Ombre(
    openai_key="your-openai-key",
    mistral_key="your-mistral-key",
    groq_key="your-groq-key",
)

# If OpenAI goes down Ombre silently routes to Mistral
response = ai_multi.run("Your prompt here", model="auto")
print(f"Provider used: {response.provider}")
print(f"Automatic fallback active: True")

# Hallucination detection on every response
response = ai.run("Tell me about recent AI research")
print(f"Hallucinations caught: {response.hallucinations_caught}")
print(f"Confidence score: {response.confidence}")

# Export compliance report
ai.export_audit(
    "mistral_audit.json",
    format="json"
)
