import os


def get_mod_name(filepath: str) -> str:
    base = os.path.basename(filepath).replace(".jar", "")
    base = base.split("-0")[0].split("-1")[0]
    return base.replace("_", " ").title()
