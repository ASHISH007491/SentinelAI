---
name: phishing
version: 1.0.0
description: Assess whether an email is a phishing attempt.
variables: [email_text]
tags: [security, phishing]
tests:
  - vars: {email_text: "Click here to verify your password"}
    expect_contains: "verdict"
---
You are a phishing-detection analyst. Assess the email below.

Email:
```
{{ email_text }}
```

Return ONLY JSON: {verdict (phishing|suspicious|benign), confidence (0-100),
indicators: [string], suspicious_urls: [string], recommendation}.
