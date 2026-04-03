# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅ Current release |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainers or use GitHub's private vulnerability reporting feature
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a fix timeline.

## Security Considerations

### Network Code
The TCP/IP multiplayer implementation (`SRC/MMULTI.C`) accepts network connections. When hosting a game:
- Only host on trusted networks
- The protocol does not include encryption or authentication
- Packet size limits are enforced to prevent buffer overflows

### API Credentials
- FLUX.2-pro and GPT Audio API keys are stored in `.env` (gitignored)
- Never commit `.env` or hardcode API keys in source files
- The asset generation tools load credentials from `.env` at runtime only

### Legacy Code
This is a port of 1996-era C code. Known limitations:
- Many fixed-size buffers without bounds checking
- `sprintf` used in places where `snprintf` would be safer
- Integer overflow possible in some math operations
- The CON script interpreter executes game scripts without sandboxing
