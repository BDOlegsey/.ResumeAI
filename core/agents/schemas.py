import json
import os
from jsonschema import Draft7Validator

from django.conf import settings

SCHEMA_PATH = os.path.join(settings.BASE_DIR, 'schema.json')

def load_schema():
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

SCHEMA = load_schema()
VALIDATOR = Draft7Validator(SCHEMA)

def validate_json_payload(payload: dict):
    errors = sorted(VALIDATOR.iter_errors(payload), key=lambda e: e.path)
    messages = []
    for e in errors:
        path = ".".join([str(x) for x in e.path])
        messages.append(f"{path or '<root>'}: {e.message}")
    return messages
