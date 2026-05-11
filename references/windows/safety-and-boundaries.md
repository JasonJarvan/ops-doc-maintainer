# Safety and Boundaries

- Prefer read-only commands and PowerShell queries. Never write to the registry or modify system configuration.
- If a command is missing or access is denied, record partial status and continue.

Redact secrets:

- do not store passwords, tokens, or API keys
- do not store private keys or certificates
- do not store complete proxy credentials or VPN pre-shared keys

For VPN/proxy tools (Clash, WireGuard, etc.), record only:

- process name and PID
- whether the system proxy is enabled and the server:port value
- TUN/TAP adapter name and status
- listening ports associated with the proxy process

For Windows Services, record only:

- service name and display name
- running status and start type

For WinRM, record only:

- enabled / disabled state
- start type

For IIS, record only:

- site name and state (Started / Stopped)

For Docker, record only:

- running containers: name, image, published ports, status
- server version

For startup items and scheduled tasks, record only:

- name and command/path
- location or task path
- associated user when available
