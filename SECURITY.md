# Security

## Supported Use

Delphic AI is designed to run locally on `127.0.0.1`. It does not include user
accounts, authentication, rate limiting, or the privacy controls needed for a
publicly hosted multi-user service.

Making the source repository public is different from exposing the running
Flask server to the internet. Do not bind the app to a public network interface
or deploy it as a public service without adding authentication, per-user data
isolation, abuse controls, and a production security review.

## API Keys

- Never commit `.env` or a real provider key.
- Entering a key in the app keeps it in server memory for the current process.
- A key placed in `.env` stays on that computer and should have private file
  permissions.
- If a key is ever committed, posted, or included in a build, revoke it with
  the provider immediately. Deleting it from the latest file is not enough
  because Git history preserves old commits.
- Every person who downloads Delphic AI should use their own provider key.

## Release Trust

Verify release checksums before running downloaded files. A macOS build should
be signed with a Developer ID certificate and notarized by Apple before it is
presented as a trusted public download. Windows builds should likewise be code
signed before they are presented as trusted public executables.

## Reporting a Vulnerability

Do not open a public issue containing a vulnerability, API key, or personal
information. Use GitHub's private security advisory feature for this repository.
