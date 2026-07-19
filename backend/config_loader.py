import json
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    with open(path) as f:
        return json.load(f)

def save_config(cfg, path=None):
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)

config = load_config()
