# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Model & Sandboxing Boundaries

Cord is designed to provide a high-level, safe, domain-specific programming environment for Discord bots.

### Controlled Execution
- Cord scripts are parsed into an Abstract Syntax Tree (AST) and executed via a controlled, tree-walking AST interpreter.
- Cord **never** evaluates scripts using unrestricted `eval()` or `exec()`.
- Standard Cord scripts do **not** have direct access to Python modules like `os`, `sys`, `subprocess`, or low-level sockets unless explicitly exposed by host adapters.

### Security Caveats
- A custom tree-walking interpreter in Python reduces the attack surface but does not constitute an impenetrable hypervisor or OS-level container.
- Untrusted multi-tenant execution should still be sandboxed with containerization (Docker, gVisor, or cgroups) and resource limits (CPU/memory caps).

### Secret & Token Safety
- Never hardcode Discord bot tokens in `.cord` source files or Git repositories.
- Cord reads secrets exclusively from system environment variables or `.env` files.
- Cord's error logger and CLI censor token strings to prevent accidental leaks in terminal logs or crash dumps.

## Reporting a Vulnerability

If you discover a security vulnerability within Cord, please do **NOT** open a public issue.

Please report the vulnerability privately via GitHub Security Advisories or by emailing the project maintainers directly. You will receive an acknowledgment within 48 hours and a coordinated disclosure timeline.
