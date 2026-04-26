"""
Ombre + Anthropic/Claude Integration
=====================================
Use Ombre as the security, caching, and audit layer
on top of your Claude applications.
"""

from ombre import Ombre

# Initialize with Anthropic key
ai = Ombre(anthropic_key="sk-ant-...")

# Claude runs through Ombre pipeline
response = ai.run(
    prompt="Analyze this contract for legal risks",
    model="claude-3-5-sonnet-20241022",
)

print(f"Response: {response.text}")
print(f"Confidence: {response.confidence}")
print(f"Audit ID: {response.audit_id}")
print(f"Threats blocked: {response.threats_blocked}")
print(f"Cost saved: {response.cost_saved}")
