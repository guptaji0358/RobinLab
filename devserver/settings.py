"""Token / secret loading: environment first, then `.dev.vars`."""

import os


def load_var(project_root: str, name: str) -> str | None:
    """Read a setting from the environment, then from `.dev.vars`."""
    value = os.environ.get(name)
    if value:
        return value.strip()

    dev_vars = os.path.join(project_root, ".dev.vars")
    if os.path.isfile(dev_vars):
        with open(dev_vars, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == name:
                    return value.strip().strip("'\"") or None
    return None


def load_token(project_root: str) -> str | None:
    return load_var(project_root, "HF_TOKEN")
