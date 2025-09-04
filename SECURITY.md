# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| 0.1.x   | :warning: Limited  |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take the security of AI Chatbot System seriously. If you have discovered a security vulnerability, please follow these steps:

### 1. Do NOT Create a Public Issue

Security vulnerabilities should **never** be reported through public GitHub issues.

### 2. Email Security Report

Please email your findings to: **cbratkovics@gmail.com**

Include the following information:
- Type of vulnerability
- Full paths of source files related to the vulnerability
- Step-by-step instructions to reproduce
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability

### 3. Response Timeline

- **Initial Response**: Within 48 hours
- **Vulnerability Confirmation**: Within 7 days
- **Fix Timeline**: Depends on severity
  - Critical: 24-48 hours
  - High: 3-5 days
  - Medium: 1-2 weeks
  - Low: Next release

### 4. Disclosure Policy

- Security issues are fixed in private
- Once fixed, a security advisory will be published
- Credit will be given to reporters (unless anonymity is requested)

## Security Best Practices

When using AI Chatbot System:

1. **API Keys**: Never commit API keys to version control
2. **Environment Variables**: Use `.env` files and keep them in `.gitignore`
3. **JWT Secrets**: Use strong, unique secrets in production
4. **Rate Limiting**: Configure appropriate rate limits for your use case
5. **HTTPS**: Always use HTTPS in production
6. **Updates**: Keep dependencies up to date

## Dependencies

We use automated tools to monitor dependencies:
- Dependabot for dependency updates
- Safety for security vulnerability scanning
- Bandit for code security analysis

## Compliance

This project aims to comply with:
- OWASP Top 10 security practices
- CWE/SANS Top 25 Most Dangerous Software Errors

Thank you for helping keep AI Chatbot System secure!
