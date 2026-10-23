# vivirsinprivilegios

Blog para ayudar a todos los migrantes en España a luchar contra el racismo estructural

## Monitor del BOE

El monitor necesita Python y la dependencia `requests`. En una instalación nueva:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r monitor/requirements.txt
.venv/bin/python monitor/run.py 2026-10-01
```

La fecha inicial también se puede indicar con `--desde 2026-10-01`. Si `.venv` ya
existe, usa su intérprete con `-m pip` como arriba; evita ejecutar directamente
`.venv/bin/pip`, que puede conservar la ruta de un entorno virtual anterior.
