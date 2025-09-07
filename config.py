import json
with open("config.json") as f:
    config = json.load(f)

OPENAI_KEY = config["OPENAI_API_KEY"]
RFEM_KEY = config["RFEM_API_KEY"]
