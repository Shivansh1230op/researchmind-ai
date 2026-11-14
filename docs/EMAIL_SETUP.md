# Email OTP signup

For guided Gmail setup on Windows, double-click **Setup Gmail Email.cmd** in the project folder. It asks for the sender address and masks the App Password, then saves the settings in the ignored local `.env` without displaying credentials. Restart the backend afterwards. Gmail host/port/TLS defaults are already configured in this checkout; the sender address and App Password must still be supplied.

Signup: name/email/password → emailed six-digit code → verified account and login session. No account is created before verification. Existing users can still sign in.

Configure the sender in the private root `.env` file:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-provider-app-password
SMTP_FROM_EMAIL=your-sender@gmail.com
SMTP_STARTTLS=true
SMTP_USE_SSL=false
```

For Gmail, use an App Password with two-step verification enabled, not your normal account password. For other providers, use their SMTP host, credentials and an authorized sender. Keep credentials out of frontend files and chat. Restart the backend after changing `.env`. Gmail instructions: https://support.google.com/accounts/answer/185833

For port 465, set `SMTP_USE_SSL=true` and `SMTP_STARTTLS=false`. Plaintext SMTP is rejected. Apply the additive migration with `python -m alembic upgrade head` in the project virtual environment with `DEBUG=false`. Development startup also creates missing tables.

Codes expire after ten minutes and are stored only as salted scrypt hashes. Codes never appear in API responses or logs. Five incorrect attempts lock a challenge. Resend replaces the old code; cooldown is 60 seconds, with six sends per email per hour. SMTP failures return an error and retain the cooldown. Delivery may take time or land in spam.

Without SMTP settings, signup reports that email verification is unavailable. There is no fake delivery or verification bypass. Tests mock delivery and verify the lifecycle; real mailbox delivery must be checked after configuring the sender. The existing deployment supports one API process; distributed scaling requires a shared limiter and email queue.
