import os

from mineai.constants import LOOSE_JSON_SEARCH_DIRS


def discover_jar_files(mc_dir: str) -> list[str]:
    mods_dir = os.path.join(mc_dir, "mods")
    if not os.path.isdir(mods_dir):
        return []
    return [os.path.join(mods_dir, f) for f in os.listdir(mods_dir) if f.endswith(".jar")]


def discover_loose_lang_files(mc_dir: str) -> list[str]:
    found: list[str] = []
    for rel in LOOSE_JSON_SEARCH_DIRS:
        base = os.path.join(mc_dir, rel.replace("/", os.sep))
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for name in files:
                if name.lower() == "en_us.json":
                    found.append(os.path.join(root, name))
    return found


def discover_snbt_files(mc_dir: str) -> list[str]:
    quests = os.path.join(mc_dir, "config", "ftbquests", "quests")
    if not os.path.isdir(quests):
        return []
    result: list[str] = []
    for root, _, files in os.walk(quests):
        for name in files:
            if name.endswith(".snbt"):
                result.append(os.path.join(root, name))
    return result
