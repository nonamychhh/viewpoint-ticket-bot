import json
def load_config() -> dict:
    with open("data/config.json","r",encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open("data/config.json","w",encoding="utf-8") as f:
        json.dump(config,f,ensure_ascii=False,indent=4)