# Security — frequently asked questions

Polski: [FAQ-bezpieczenstwo.md](FAQ-bezpieczenstwo.md)

Short answers, no technical jargon: what the audit does with your GetResponse or MailerLite account, what the AI assistant (Claude) sees, and how to check it yourself.

## Do my contacts end up with the AI or with Anthropic?

No. The audit doesn't fetch your contact list or any buyer data — so there's nothing of that kind to pass on. What reaches Claude (Anthropic's AI model) is only the content of the report: the names of your lists, automations and forms, email subjects, and numbers (how many sent, how many clicks, how many orders). That's your company's data, not your customers'.

If you don't want anything from your account to reach the AI — not even those names and numbers — use [no-AI mode](../README.en.md#no-ai-mode).

## Can the script see my customers' email addresses?

No. The script can read only selected places in the API: statistics, settings and the content of your emails. The list of those places is in the code (`DOZWOLONE_SCIEZKI`), and any attempt to read anything else — a contact list, for example — stops the audit. From every response only the fields the audit needs are kept, and the rest is dropped before anything is written to disk.

Two details:

- **Orders in GetResponse** are read with only these fields: order number, amount, date, status, and whether the order is linked to a contact (yes / no). No buyer name, address or email.
- **Orders in MailerLite** are not read at all, because the MailerLite API always returns them together with the buyer's data. The order count and revenue come from the store's summary report, which contains numbers only.

If you typed an email address, phone number or IP address into a list name or email subject yourself, the script masks it ("[e-mail ukryty]" — "email hidden") before saving anything to disk.

## Why does the API key have full access to my account?

Because GetResponse and MailerLite don't let you create a read-only key — every key from the panel can do everything you can. "Read-only" describes our script: it sends only read requests and changes nothing.

That's why we recommend:

- create a **separate key just for the audit** (e.g. named "audyt"),
- **delete it right after the audit** in the same place in the panel,
- never paste the key into the chat.

In MailerLite you can also restrict the token to your IP address.

## What if the AI does something other than the script?

Claude Code runs commands on your computer, so technically it could call the API in some other way than through the script. The skill explicitly forbids it: it may not call the GetResponse or MailerLite API outside the script, connect to them through other tools, or read the key — even if you ask it to. But that is a rule, not a hard block.

What actually protects you:

- with default settings, Claude Code asks for permission before running a command — you see what you approve,
- a separate key deleted right after the audit: once it's deleted, nobody can do anything with it,
- [no-AI mode](../README.en.md#no-ai-mode): you run the script yourself and no AI is involved at all.

## Can I use the audit without AI?

Yes. Download the repository and run the script yourself in a terminal — instructions in the [README, "No-AI mode" section](../README.en.md#no-ai-mode). The `.md` report and the PDF are created on your computer and nothing reaches any AI model. All you need is Python 3.8 or newer. Without a key you can look at a sample report first: add `--pokaz`.

## What does the AI see from my account?

Only what's in the report:

- names of lists (groups) and the number of contacts on each — without the contacts themselves,
- contacts gained and lost during the audit period, signup sources and removal reasons (numbers only),
- names of automations, whether they're on, and how many people went through them,
- email subjects and their results: sent, opens, clicks, unsubscribes, spam complaints, bounces,
- for the welcome series: whether each email is sales-driven, value-driven or mixed, with a short reason (e.g. "discount code, percentage") — the email body itself doesn't go into the report,
- names of signup forms, their views, signups and conversion rate,
- the store name, currency, number of orders and revenue in the audit period, and how many orders have no linked contact,
- in GetResponse: the domain of the sender address (e.g. "@yourstore.com", without the part before "@") and warnings about its settings,
- whether emails have sales tracking turned on.

A first or last name could appear there only if you typed it yourself into a list, automation, form or store name, or an email subject. No program can tell "Jan Kowalski" apart from a product name, so such names are not masked.

## Does the report contain my customers' data?

No: no email addresses, names, phone numbers, postal addresses or IP addresses of customers and buyers. The report contains names and numbers from your account (see the question above). Before you send it to anyone, just look over the list names and email subjects — if you typed someone's name into them, it will be visible in the report too.

## Is the data sent or stored anywhere?

- **Sent:** the script connects only to the official GetResponse or MailerLite API, over an encrypted connection. There are no usage statistics and nothing is sent to us. The script rejects other addresses and redirects.
- **Stored on your computer:** the `.md` and `.pdf` report in the current directory, a progress file (stages and counters only), and — if you ask for it — a `.json` file with the same data as the report.
- **Cache:** so that an interrupted audit doesn't start from scratch, the script keeps trimmed API responses (without personal data) for 12 hours in the system's temporary directory, accessible only to your user. Anything older than 12 hours is deleted on the next run.
- **With Claude Code:** the content of the report goes into the conversation with Claude, like any file Claude reads. How conversations are retained is governed by your Claude account and your agreement with Anthropic.

## GDPR: do I need a data processing agreement?

We don't give legal advice — that decision is yours or your adviser's. These facts will help you make it:

- **In no-AI mode** your customers' data doesn't leave your computer: the script connects only to your GetResponse or MailerLite account and doesn't fetch contacts' or buyers' personal data at all.
- **With AI (Claude Code)** only your company's data reaches the model — names of lists and automations, email subjects and numbers — without your customers' personal data. Exception: a first or last name you typed yourself into a list name or email subject (see above).
- The author of the tool receives no data from your account.

## How can I check this myself?

Run the "canary" test — no key, no internet, a dozen or so seconds:

```bash
python3 tests/test_kanarek.py -v
```

The test fakes the GetResponse and MailerLite APIs for every place the script is allowed to read and fills every field of every response with made-up personal data (e.g. `kanarek-17@example.com`, `+48 600 000 017`, `203.0.113.17`, "Jan Kanarek17"), including fields the audit doesn't use. Then it runs the full audit and the PDF step and checks that none of those addresses, phone numbers or IP addresses appeared on screen, in the report, in the JSON file, in the PDF, in the progress file or in the on-disk cache. At the end it lists the fields where a first and last name can pass through (only names and subjects typed by the account owner).

Code to review:

- the test: [tests/test_kanarek.py](../tests/test_kanarek.py),
- the scripts: [GetResponse](../skills/audyt-getresponse/scripts/audyt_getresponse.py), [MailerLite](../skills/audyt-mailerlite/scripts/audyt_mailerlite.py), [shared filter and masking](../skills/audyt-getresponse/scripts/wspolne.py),
- full review (in Polish): [docs/BEZPIECZENSTWO-przeglad.md](BEZPIECZENSTWO-przeglad.md),
- reporting a problem: [SECURITY.md](../SECURITY.md).
