![Cover](https://cdn.hashnode.com/res/hashnode/image/upload/v1754984174396/e54c2cf0-9c4c-460c-a956-6254ef249b71.png)

Your contact page or your newsletter form is all set, ready for new visitors.  
You launch your website, and after a few days **here comes the drama**: **1000 form submissions**, all by the same bot activity.

*I know I’m not that famous to reach those numbers 🫠* Let’s check the my dashboard one second…

![](https://cdn.hashnode.com/res/hashnode/image/upload/v1754673240296/1c973ad5-076a-4ccb-9ea3-90bba5473a89.png)

What a funny guy that RobertMow and his **990 SUBMISSIONS**  
You know where this is going: **let’s secure our endpoint!**

In this tutorial we’ll go over 7 tips and their implementation to prevent bot form submissions.

1. ### Flag bots IP addresses
    

When an activity can only be a bot, we can flag IP addresses by storing them as malicious. The storage mechanism depends on your stack:

* On Cloudflare Workers, use KV (key-value datastore)
    
* On any other backend, use server-side session
    

We’ll see how we can notice a bot activity in the next steps.  
Once the ip address if flagged, ignore any form sumbit:

```typescript
// prevent bots from re-submitting a form
const KV = context.cloudflare.env.KV;
const ipKey = `contact_ip_${clientIP}`;
if (await KV.get(ipKey)) {
  console.warn(`IP ${clientIP} has been flagged as a bot`);
  return Response.json({ success: true });
}
```

2. ### Prevent bypassing client-side validation
    
    If not alrejady done, please ensure your form is validated on client-side.  
    In addition, if the value sent to the server isn’t validated, that means client-side validation has been bypassed and should be flagged as malicious.
    

```typescript
if (!(await schema.validate(data))) {
  console.warn("Client-side form validation bypassed");
  await KV.put(ipKey, "bot", { expirationTtl: 86400 }); // 24 hours cooldown
  return Response.json({ success: true });
}
```

3. ### Use a client nonce
    
    To prevent replay attacks, we generate a unique nonce for each form submission. This nonce is stored on backend's side and compared against the nonce provided by the client.
    

```typescript
// generate nonce on contact form page render
const timestamp = Date.now();
const randomPart = Math.random().toString(36).substring(2, 15);
const nonce = `${timestamp}.${randomPart}`;
await KV.put(nonceKey, "unused")
```

```typescript
/**
 * Validates if a nonce is valid and not expired
 * @param nonce The nonce to validate
 * @param maxAge Maximum age of the nonce in milliseconds (default: 1 hour)
 * @returns Boolean indicating if the nonce is still valid
 */
export function isNonceValid(nonce: string, maxAge: number = 3600000): boolean {
  try {
    const parts = nonce.split(".");
    if (parts.length !== 2) return false;

    const timestamp = parseInt(parts[0], 10);
    const now = Date.now();

    // Check if nonce has expired
    return now - timestamp <= maxAge;
  } catch (error) {
    return false;
  }
}

...

if (!isNonceValid(nonce)) {
  console.warn("Expired nonce detected");
  return Response.json({
    success: false,
    error: t("contact.response.error.sessionExpired"),
  });
}
const nonceKey = `contact_nonce_${nonce}`;
const nonceState = await KV.get(nonceKey);
if (nonceState === "unused") {
  await KV.put(nonceKey, "used");
} else if (nonceState === "used") {
  console.warn("Duplicate form submission");
  return Response.json(
    {
      success: false,
      error: "The form has already been submitted"
    },
    { status: 409, headers: { "Content-Type": "application/json" } }
  );
} else {
  console.warn("Invalid nonce");
  return Response.json(
    {
      success: false,
      error: "Invalid nonce submitted"
    },
    { status: 409, headers: { "Content-Type": "application/json" } }
  );
}
```

4. ### Cloudflare Rate Limiting
    

We use [Cloudflare's Rate Limiting API](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/) to restrict the number of form submissions from a single IP address. **Note 1**: This is not perfect as users on mobile networks often have the same IP address. **Note 2**: The rate limiting API is still in open beta (August 2025).

```typescript
// Implementation in index.tsx
const rateLimiter = context.cloudflare.env.RATE_LIMITER_CONTACT;
const clientIP = request.headers.get("CF-Connecting-IP") || "";
const rateLimitResult = await rateLimiter.limit({ key: `contact_form_${clientIP}`});
if (!rateLimitResult.success) {
  // Return 429 Too Many Requests
}
```

The Rate Limiter needs to be bound to your Cloudflare Worker environment. This is typically done in your `wrangler.toml` file:

```toml
[env.production]
kv_namespaces = [
  { binding = "RATE_LIMITER_CONTACT", id = "unique-namespace-id" }
]
```

5. ### Honeypot Field
    

A hidden field called "website" is included in the form. This field is invisible to human users but will likely be filled out by bots. If the field contains any data, the submission is silently rejected.

```typescript
// Check honeypot field - if it contains data, it's likely a bot
const honeypotField = data.website?.toString();
if (honeypotField) {
  console.warn("Honeypot field triggered");
  await KV.put(ipKey, "bot", { expirationTtl: 86400 }); // 24 hours cooldown      
  // Return success to avoid giving bots feedback, but don't process the form
  return Response.json({ success: true });
}
```

6. ### CAPTCHA Integration (hCaptcha)
    

The form includes an hCaptcha challenge to verify that the user is human. We use the official React component from [@hcaptcha/react-hcaptcha](https://www.npmjs.com/package/@hcaptcha/react-hcaptcha).

```typescript
// In the form component
<HCaptcha
  ref={captchaRef}
  sitekey={process.env.HCAPTCHA_SITE_KEY || "10000000-ffff-ffff-ffff-000000000001"}
  onVerify={(token) => setCaptchaToken(token)}
/>

// In the submission handling
const captchaResult = await validateCaptcha(data.hCaptchaToken.toString());
if (!captchaResult.success) {
  return Response.json({
    success: false,
    error: "CAPTCHA verification failed",
  });
}
```

hCaptcha requires a site key and secret key to be set as environment variables in the `.env` file (locally) and in your `wrangler.jsonc` file (on Cloudflare Workers).

* `HCAPTCHA_SITE_KEY` - Your hCaptcha site key for frontend integration
    
* `HCAPTCHA_SECRET_KEY` - Your hCaptcha secret key for verification
    

7. ### Email Validation with Mailchecker
    

We use the [mailchecker](https://www.npmjs.com/package/mailchecker) library to validate email addresses and detect disposable email services. It is backed by a database of over 55,000 throwable email domains.

```typescript
// Validate email with mailchecker
const email = data.email?.toString() || "";
if (email && !mailchecker.isValid(email)) {
  return Response.json({
    success: false,
    error: "Please use a valid email address",
  });
}
```

Additionally, email validation is also included in the Yup schema:

```typescript
email: yup
  .string()
  .email(messages.email.invalid)
  .required(messages.email.required)
  .test(
    "is-valid-email",
    "Email appears to be invalid or disposable",
    (value) => (value ? mailchecker.isValid(value) : true)
  ),
```

8. ### Avoid false positive
    
    I do not suggest using content filtering, for example on keywords (“nigerian”, “prince”) as this may result in false positives.
    

# Quick summary

If you’re in a hurry, captchas can still be a decent option — most bots don’t handle them well.  
Just make sure you check the captcha value on the server so it can’t be skipped.

That’s what’s worked for me against spam, hopefully it’s useful for you too.

Have you run into malicious activity, DDoS attacks, or spammed forms?  
I’m curious how you solved it — and I wouldn’t mind hearing the weird or funny stories that came with it.