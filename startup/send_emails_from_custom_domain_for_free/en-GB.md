![Cover](https://cdn.hashnode.com/res/hashnode/image/upload/v1754991420922/b68ad27b-3789-4015-affe-70bc5a650dce.png)

Using a custom domain email like [contact@yourcompany.com](mailto:contact@yourcompany.com) instantly boosts your credibility. Let’s be honest — [john.doe@gmail.com](mailto:john.doe@gmail.com) doesn’t exactly scream “trust me with your money.”

This guide shows how to:

* ✅ Receive emails at your preferred inbox (e.g., Gmail)
    
* ✅ Send emails as your custom domain address
    
* ✅ Do it all for **free**
    

## Why not the usual options?

1. **Cloudflare Email Routing**: Great for forwarding, but doesn’t support sending.
    
2. **Self-hosted mail server**: Technically cool. Realistically, a nightmare to maintain unless you love configuring postfix, dovecot, SPF, DKIM, DMARC, and debugging why mail isn't delivered. This will keep us away from installing all these:
    
    * MTA (Mail Transfer Agent): Handles the sending and receiving of emails via the SMTP protocol.
        
    * MDA (Mail Delivery Agent): Delivers received emails to users' inboxes.
        
    * MUA (Mail User Agent): The email client used to read and send emails.
        
    * POP3/IMAP Server: Allows users to access their emails remotely.
        
    * Webmail: Web interface for accessing emails.
        
3. **Google Workspace, Zoho, etc.**: Solid, but we’re keeping costs at zero. Zoho Mail's free plan is suitable for small teams but has limited flexibility:
    
    * Up to 5 users (including the SuperAdmin account)
        
    * max 50 emails per day per user
        
    * **no email forwarding**
        
    * limited spam filtering.
        

I typically set up a few standard addresses for each custom domain, and before you know it, the number of email addresses starts to pile up quickly.

## The free stack: [forwardemail.net](http://forwardemail.net) + Gmail

We’ll use:

* [forwardemail.net](http://forwardemail.net) to handle inbound mail
    
* **Gmail’s “send as” feature** to send emails from your domain. Just keep in mind that you're still subject to Gmail’s free account limits: up to 500 emails per 24 hours, and 100 recipients per message. Each teammate gets their own quota as they use their own gmail account.
    

---

In the paid plans, forwardemail offers **email aliases**. These aliases can be used in any email client for your emails to be **send-as your custom-domain email**. When using those aliases, the outbound email server are sent through Forward Email SMTP server.

If your team may grow, I recommend to take the paid plan at $3/month which gives access to forwardemail web interface to setup the aliases.

As I’m a solo freelance dev, I’ll just stick with the free plan. We will not use forwardemail alises, and we will send the emails through Google outbound SMTP server.

**Note:** If your domain has been created less than 90 days, you must pay $3/month until the 90 days period ends. This is due to abuse prevention controls to block suspicious activity regarding registrars like GoDaddy, Namecheap, and Hostgator

## [forwardemail.net](http://forwardemail.net) setup

1. Create an account on [forwardemail.net](http://forwardemail.net) and register your custom domain.
    
2. Set DNS entries on your preferred DNS provider.
    

| Type | Name | Content | Proxied |
| --- | --- | --- | --- |
| MX | @ | mx1.forwardemail.net | DNS only |
| MX | @ | mx2.forwardemail.net | DNS only |
| TXT | @ | "forward-email-site-verification=XXXXXX" | DNS only |

3. Setup email forwarding In the free plan, email forwarding rules are set in DNS entries. Fortunately, [forwardemail.net](http://forwardemail.net) allows to encrypt records at no cost.
    

**Note:** Use [https://forwardemail.net/encrypt](https://forwardemail.net/encrypt) to encrypt these values and avoid exposing your Gmail in plain text.

To forward all emails from your domain to a single address:

| Type | Name | Content | Proxied |
| --- | --- | --- | --- |
| TXT | @ | forward-email=user@gmail.com | DNS only |

To forward a single email address (e.g., [hello@example.com](mailto:hello@example.com) to [user@gmail.com](mailto:user@gmail.com)):

| Type | Name | Content | Proxied |
| --- | --- | --- | --- |
| TXT | @ | forward-email=hello:user@gmail.com | DNS only |

To forward multiple specific emails, separate each with commas:

| Type | Name | Content | Proxied |
| --- | --- | --- | --- |
| TXT | @ | forward-email=hello:user@gmail.com,support:user@gmail.commailto:user@gmail.com | DNS only |

You can have multiple TXT records to set multiple forwarding rules without exceeding 255 characters per line.

**Example encryption** Here I want to forward all emails to [user@gmail.com](mailto:user@gmail.com):

![Encrypt TXT Record](https://sonicjs-r2.gloweet.com/1753963325268-grafik.png)

Click Encrypt. A popup opens with the record's content: forward-email=XXXXXXXXXXXX

Register the DNS record in your DNS provider:

| Type | Name | Content | Proxied |
| --- | --- | --- | --- |
| TXT | @ | "forward-email=XXXXXXXXXXXX" | DNS only |

You should already be able to receive emails sent to your domain in your gmail account.

**Onboard a new user**

Let's say a new user arrives in your team. His email is [john@gmail.com](mailto:john@gmail.com). To ensure he receives emails from [john@yourcustomdomain.com](mailto:john@yourcustomdomain.com), just add the following TXT entry after having encrypted it: forward-email=john:[john@gmail.com](mailto:john@gmail.com)

## Send Emails as Your Domain (Gmail)

1. Enable **Two-Factor Authentication** on your Gmail.  
    Visit [https://www.google.com/landing/2step/](https://www.google.com/landing/2step/) if you do not have it enabled.
    
2. Go to: [https://myaccount.google.com/apppasswords  
    Generate](https://myaccount.google.com/apppasswords%EF%BF%BCGenerate) an App Password for "Mail".
    
3. Type in the email you want to send-as and click Create
    
    A popup appears with the generated app password. Copy it.
    
    **Important**: If you are using G Suite, visit your admin panel &gt; Apps &gt; G Suite &gt; Settings for Gmail &gt; Settings, and make sure to check *"Allow users to send mail through an external SMTP server..."*.  
    There will be some delay for this change to be activated, so please wait a few minutes.
    
4. In Gmail, go to:  
    **Settings &gt; See all settings &gt; Accounts and Import &gt; Send mail as**
    
5. In the Send email as section, make sure you check Reply from the same address to which the message was sent, then click Add another email address.
    
    * Name: whatever you want
        
    * Email: your custom domain address (e.g., [contact@yourdomain.com](mailto:contact@yourdomain.com))
        
    * Uncheck “Treat as alias"
        
        ![Add domain email to gmail](https://sonicjs-r2.gloweet.com/1753963619627-grafik.png)
        
6. SMTP Config:
    
    * SMTP Server: [smtp.gmail.com](http://smtp.gmail.com)
        
    * Port: 587
        
    * Username: your original gmail address **without the** [**gmail.com**](http://gmail.com) (e.g. just "john.doe" if my email is "[john.doe@gmail.com](mailto:john.doe@gmail.com)")
        
    * Passord: the app password
        
    * TLS: yes
        
        ![SMTP Config](https://sonicjs-r2.gloweet.com/1753963920655-grafik.png)
        
7. Gmail sends a confirmation email. Click the link inside. Done!
    

### Test It

**Compose a new email in Gmail**: Open Gmail &gt; Compose.

Your new address should be available in the “From” dropdown.

![Email dropdown](https://sonicjs-r2.gloweet.com/1753964011482-grafik.png)

The email should be received on the other end!

## Quick Summary

With a few DNS changes and Gmail tweaks, you get:

* Professional-looking emails
    
* Centralized inboxes
    
* Zero hosting or subscription costs
    

Ideal for small teams, personal projects, or anyone who wants a professional touch—without opening their wallet.

I’d love to hear how you manage custom domain emails. Are you using something similar, or have a completely different setup? Drop it in the comments!