#!/usr/bin/env python3
"""Copia as Repository Variables do GitHub para o wrangler.toml do deploy."""

import json
import os
import re
import sys
from pathlib import Path


TRACKING_VARIABLES = (
    "WAYBILL_NO",
    "WAYBILL_LABELS",
    "JADLOG_CTE",
    "JADLOG_LABELS",
    "LOGGI_CODES",
    "LOGGI_LABELS",
    "CORREIOS_CODES",
    "CORREIOS_LABELS",
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("uso: sync_worker_vars.py CAMINHO_WRANGLER_TOML")

    raw_variables = os.environ.get("REPOSITORY_VARS_JSON")
    if raw_variables is None:
        raise SystemExit("REPOSITORY_VARS_JSON nao foi definido")

    repository_variables = json.loads(raw_variables)
    missing = [name for name in TRACKING_VARIABLES if name not in repository_variables]
    if missing:
        raise SystemExit("Repository Variables ausentes: " + ", ".join(missing))

    config_path = Path(sys.argv[1])
    config = config_path.read_text(encoding="utf-8")

    for name in TRACKING_VARIABLES:
        value = json.dumps(str(repository_variables[name]), ensure_ascii=False)
        pattern = re.compile(rf"^{re.escape(name)}\s*=.*$", re.MULTILINE)
        config, replacements = pattern.subn(f"{name} = {value}", config)
        if replacements != 1:
            raise SystemExit(
                f"esperava exatamente uma declaracao de {name}, encontrei {replacements}"
            )

    with config_path.open("w", encoding="utf-8", newline="\n") as config_file:
        config_file.write(config)

    print("Variaveis de rastreio sincronizadas: " + ", ".join(TRACKING_VARIABLES))


if __name__ == "__main__":
    main()
