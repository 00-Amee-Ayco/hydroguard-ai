"""Run one synthetic Critic request only when a Nemotron route is discovered."""
import json
import os
from dotenv import dotenv_values
from hydroguard.ai.meterless import RuntimeSettings, parse_connection, MeterlessError
from hydroguard.ai.nightshift_smoke import verify


def load_configuration():
    # Explicit precedence: process > .env.local > .env > private provider settings.
    values = {**dotenv_values('.env', interpolate=False),
              **dotenv_values('.env.local', interpolate=False), **os.environ}
    stored = RuntimeSettings().load()
    base = values.get('NIGHTSHIFT_BASE_URL') or stored.base_url
    token = (values.get('NIGHTSHIFT_API_KEY') or values.get('METERLESS_RUNTIME_TOKEN')
             or stored.token)
    return parse_connection(base, token), values.get('NIGHTSHIFT_MODEL') or None


def main():
    try:
        connection, model = load_configuration()
        result = verify(connection, model)
    except (MeterlessError, OSError):
        result = {'connection': 'BLOCKED', 'nemotron_invocation': 'BLOCKED',
                  'blocker': 'invalid_or_unreadable_configuration_details_omitted'}
    print(json.dumps(result, indent=2))
    return 0 if result['nemotron_invocation'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
