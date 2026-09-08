# Accounts

## Students

The local demo exposes the student entrance at `http://127.0.0.1:8765/#/student`.
Choose "登录 / 我的账号", then "注册". Enter a nickname, email and a password
of at least eight characters. Registration creates a student account only; sign
in afterwards. Browsing published requirements does not require an account.

The student build exposes the same account page at `/#/account`. Owner builds
keep their separate surface unless `VITE_ENABLE_STUDENT_ENTRY=true` is explicitly
enabled, as in the loopback-only demo launcher. API authorization is enforced
regardless of which frontend is used. Students cannot review, publish, upload,
manage integrations, or access partner submissions.

## Administrators

There is no public administrator registration. The repository operator creates
an account from the terminal, with the password entered privately:

```sh
.venv/bin/python -m scripts.create_admin --local-demo --email owner@example.com
```

Omit `--local-demo` only when intentionally using the configured application
database. Existing accounts are never overwritten by this command. Existing
`OWNER_EMAIL` / `OWNER_PASSWORD` deployment provisioning remains supported.

The local demo accepts `demo` as an alias for its existing `demo@localhost`
account. Credentials are stored only in ignored `runtime/local_demo/access.json`.
New installations still generate a random password; no shared password is shipped.

## Boundaries Before Public Deployment

This remains a local MVP: email ownership is not verified, and password recovery,
account deletion, persistent personal profiles and favorites are not implemented.
Add email verification, recovery, abuse/rate limiting and HTTPS-only cookies before
opening signup to the internet. A nickname is not proof of identity. Do not reuse
the local demo password for a public deployment. No admissions records are changed
or published by account registration.
