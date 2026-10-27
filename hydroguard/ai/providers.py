"""Available general chat providers. The offline evidence Critic remains separate."""
from hydroguard.ai.meterless import MeterlessProvider

CHAT_PROVIDERS = {MeterlessProvider.id: MeterlessProvider}
