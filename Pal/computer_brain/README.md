# Herbie computer coordinator

The coordinator gives the home computer a short renewable `computer-primary`
lease. Herbie's identity and writable memory stay on the Galaxy. If the process,
computer, or Wi-Fi disappears, the lease expires and the phone reports itself
as `phone-local` automatically.

It also starts an authenticated local-network language-model endpoint backed by
Ollama. The Galaxy sends it bounded conversation requests while the lease is
healthy and remains the only writer of identity and memory. It does not expose
motor commands and cannot acquire motor authority.

The current primary model is `qwen3.5:9b` with thinking disabled for ordinary
conversation. The PC prompt continues from the Galaxy's recent-dialogue and
memory context without treating stored memory as instructions. If the 15-second
lease expires, the Galaxy routes to its foreground Qwen3 1.7B service instead.

One check:

```powershell
python computer_brain\herbie_coordinator.py --once
```

Continuous coordination:

```powershell
python computer_brain\herbie_coordinator.py
```

On this Windows computer, use `tools\Start-Herbie-Coordinator.ps1` to run it
hidden with private logs under `.herbie`. The starter launches both the PC
language brain on port 18766 and the lease coordinator. Use
`tools\Stop-Herbie-Coordinator.ps1` to stop only those recorded processes.
After they stop, the phone takes over when the short lease expires.

`tools\Set-Herbie-Coordinator-Autostart.ps1` installs a current-user Windows
logon task. Run it with `-Remove` to remove that task without touching Herbie's
phone service, memory, or current coordinator process.

The last verified phone address is cached in the current user's private
`.herbie\phone-endpoint.json`. If that address changes, the coordinator scans
only the computer's current private `/24` network for a matching Herbie health
response and updates the cache.
