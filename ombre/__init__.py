"""
Ombre — The infrastructure layer that makes AI trustworthy.

Your data never leaves your infrastructure.
You bring your own API keys.
Zero required dependencies.

Quick start:
    from ombre import Ombre

    ai = Ombre(openai_key="sk-...")
    response = ai.run("Your prompt here")

    print(response.text)
    print(response.confidence)
    print(response.cost_saved)
    print(response.audit_id)

GitHub:  https://github.com/ombre-ai/ombre-core
Contact: ombreaiq@gmail.com
License: BUSL-1.1
"""

from .client import Ombre
from .response import OmbreResponse, OmbreError, OmbreBlockedError, OmbreTimeoutError, OmbreProviderError
from .config import OmbreConfig

__version__ = "1.0.0"
__author__ = "Ombre Team"
__email__ = "ombreaiq@gmail.com"
__license__ = "BUSL-1.1"

__all__ = [
    "Ombre",
    "OmbreResponse",
    "OmbreError",
    "OmbreBlockedError",
    "OmbreTimeoutError",
    "OmbreProviderError",
    "OmbreConfig",
]
