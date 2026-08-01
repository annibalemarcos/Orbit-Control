"""Serviço de demonstração: escreve uma linha no log a cada dois segundos."""

from __future__ import annotations

import os
import time
from datetime import datetime


print(f"Worker iniciado. PID={os.getpid()}", flush=True)

counter = 0
while True:
    counter += 1
    print(f"[{datetime.now().isoformat(timespec='seconds')}] pulso #{counter}", flush=True)
    time.sleep(2)
