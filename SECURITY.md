# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Current |

## Reporting a Vulnerability

If you discover a security vulnerability in docprep, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email: **yeongseon.choe@gmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Initial assessment**: Within 1 week
- **Fix and disclosure**: Coordinated with reporter

## Scope

The following are in scope for security reports:

- Code injection via config files or input documents
- Path traversal in file loading
- Denial of service via crafted input
- Dependency vulnerabilities affecting docprep functionality
- Information disclosure through error messages or exports

The following are out of scope:

- Vulnerabilities in dependencies that don't affect docprep's usage
- Issues requiring physical access to the machine
- Social engineering attacks

## Security Practices

docprep follows these security practices:

- **Bandit** security scanning runs on every commit via pre-commit hooks
- **No external network calls** — docprep processes local files only
- **No code execution** — document content is never evaluated
- **Dependency pinning** — version ranges prevent unexpected updates
- **Type safety** — mypy strict mode catches potential issues at compile time
