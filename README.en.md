# Email marketing audit for online stores

Polski: [README.md](README.md)

[![GitHub stars](https://img.shields.io/github/stars/Autilos/audyt-mailingu?style=social)](https://github.com/Autilos/audyt-mailingu/stargazers)

A Claude Code skill that checks a store's email marketing in a few minutes and tells you plainly what isn't working.

Supports **GetResponse** and **MailerLite**.

> **The report is in Polish — on purpose.** The tool is built for Polish online stores: the report, the recommendations and the skill's conversation are written for a Polish store owner. An English version of the report is not planned at the moment. This README and the [security FAQ](docs/FAQ-security.en.md) are in English so that anyone can review what the tool does and how it handles data.

## What it checks

- Whether you have the automations every store should have: welcome series, abandoned cart, post-purchase, second purchase, and win-back for inactive customers.
- Whether those automations actually work — whether anyone is going through them (a common problem: an automation is "on", but nobody has entered it for months).
- Results of every email: clicks, opens, unsubscribes, spam complaints, bounces. In GetResponse, opens and clicks exclude bots (the "human" fields from the API). In MailerLite, opens are raw (they include automatic opens, e.g. Apple Mail), so clicks are what counts there.
- How often you send newsletters and whether you are wearing out your list.
- Whether the store sends orders to the email platform at all, and how many buyers never make it onto the list (GetResponse). In MailerLite: how many orders and how much revenue the store reported during the audit period, and how much of it was attributed to emails — campaigns and automations separately — taken from the store's summary report, without individual orders.
- Whether emails have e-commerce tracking turned on (attributing sales to an email).
- **The welcome series**: how many emails, on which days, whether it runs, and whether each email is sales-driven, value-driven or mixed (judged from the words and elements in the email — discount code, percentage, prices, buttons — so it can be wrong; the reason is given next to each email).
- **Signup forms**: views, signups and conversion rate of every form.
- **List health**: contacts gained and lost during the audit period, signup sources and removal reasons (GetResponse); the state of groups — active, unsubscribed, bounced, spam (MailerLite).
- **Deliverability** (GetResponse): whether the sender domain is verified and whether there are DKIM or DMARC warnings.
- **Revenue as seen by GetResponse**, and — if you provide your store's figures — a comparison with them.

The result is a report in Polish: the most important problems first, then **recommendations in the order you should do them** (only for what was actually found), then the details. The report can be turned into a PDF: `python3 skills/audyt-getresponse/scripts/raport_pdf.py audyt-getresponse.md` (needs Chrome, Chromium or Edge; without them you get an HTML file to print).

## Try it without an API key

Want to see a report before you hand over any key? Type **„zrób pokazowy audyt”** ("run a demo audit") in Claude Code, or run the script with `--pokaz` — it works without a key and without internet access, on made-up data for a fictional tea shop:

```bash
python3 skills/audyt-getresponse/scripts/audyt_getresponse.py --pokaz --raport audyt-pokaz.md
python3 skills/audyt-getresponse/scripts/raport_pdf.py audyt-pokaz.md
```

The report is labelled at the top as a demo with made-up data. Same for MailerLite: `skills/audyt-mailerlite/scripts/audyt_mailerlite.py --pokaz`.

## The report: a PDF and a file for your AI assistant

After the audit you get two files: a **PDF** to read and pass on, and a **Markdown** file (`.md`) with the same content plus an extra section for an AI assistant — a list of problems, a checklist of tasks with where to find each setting in the panel, and what the audit did not check. You can give the `.md` file to your AI assistant (Claude, ChatGPT) or an agent to help with the fixes. Links and addresses in the PDF are clickable.

## Help after the audit

Ask in Claude Code "how do I fix this?", "who can do this for me?" or "report a bug" (the skill answers in Polish) — the `audyt-pomoc` skill splits the tasks into what you can do yourself and what is better handed off, and for a bug it prepares a report without any data from your account ([issue template](https://github.com/Autilos/audyt-mailingu/issues/new?template=blad.md)).

## Security

Don't want anything from your account to reach an AI model? Run the script yourself in a terminal — see [no-AI mode](#no-ai-mode). Common questions: [security FAQ](docs/FAQ-security.en.md).

**Your subscribers' and buyers' addresses and personal data never reach the AI.** The audit reads only statistics, settings and the content of your emails — never contact lists.

- **Read-only.** The script sends only read requests — it changes nothing, sends no emails, deletes no contacts. The code is short and open: [GetResponse](skills/audyt-getresponse/scripts/audyt_getresponse.py), [MailerLite](skills/audyt-mailerlite/scripts/audyt_mailerlite.py).
- **No contact data is fetched.** The code contains an allowlist of API paths the script may read (`DOZWOLONE_SCIEZKI`); any other path stops the audit. From every response only the numbers and names the audit needs are kept, and everything else is dropped before anything is written to disk or shown in the conversation. If a list name or email subject contains an email address, phone number or IP address, the script masks it before saving anything.
- **Orders.** In GetResponse the audit reads orders with only these fields: order number, amount, date, status, and whether the order is linked to a contact — no buyer data. In MailerLite the audit **does not read individual orders at all**: the MailerLite API always returns an order in full, including the buyer's data (email, first and last name, phone), and does not let you pick fields ([docs](https://developers.mailerlite.com/ecommerce/orders)). The order count and revenue come from the store's summary report, which contains numbers only ([docs](https://developers.mailerlite.com/ecommerce/shops)).
- **Claude has explicit rules in the skill.** It does not call the GetResponse or MailerLite API outside the audit script, does not read the key (e.g. with commands that print environment variables or config files), and does not fetch contacts or buyer data — even if you ask it to. In that case it explains that this audit doesn't do that, because customer data would end up in the AI model.
- **The key has full access to your account.** GetResponse and MailerLite have no read-only API keys — every key can do everything you can. "Read-only" describes the audit script, not the key. That's why you should:
  - create a **separate key just for the audit** (e.g. name it "audyt") — GetResponse: Menu → Integrations and API → API; MailerLite: Integrations → MailerLite API → Generate new token (there you can also restrict the token to your IP address),
  - **delete it right after the audit** in the same place, and delete the file from your computer: `rm ~/.config/audyt-mailingu/*.key`,
  - never paste the key into the chat.
- **The key goes only to GetResponse or MailerLite.** The script sends it only to the official API address, over an encrypted connection. Other addresses and redirects are rejected, and the key never appears in the report or in error messages. If you have a proxy set in environment variables (`HTTPS_PROXY`), the connection goes through it, still encrypted.
- **Results stay on your disk.** The report is an `audyt-*.md` file (and a PDF) in the current directory. In Claude Code its content (names of automations, lists, email subjects, numbers) goes into the conversation, like any file Claude reads — which is why the report contains no customer data. The PDF is generated without downloading anything from the internet.
- **What can't be ruled out technically:** a key with full access sits in an environment variable or a file on your computer, so any program you run there (including an AI assistant given other instructions) could technically read it. The skill forbids Claude from doing so, but the most reliable protection is a separate key that you delete right after the audit.
- Full review of what we checked (in Polish): [docs/BEZPIECZENSTWO-przeglad.md](docs/BEZPIECZENSTWO-przeglad.md). Reporting a problem: [SECURITY.md](SECURITY.md).

### Check it yourself

You don't have to take our word for it. The repository contains a "canary" test: it fakes the GetResponse and MailerLite APIs for every path the script is allowed to read and fills every field of every response with made-up personal data (e.g. `kanarek-17@example.com`, `+48 600 000 017`, `203.0.113.17`, "Jan Kanarek17"). Then it runs the full audit and the PDF step and checks that none of those addresses, phone numbers or IP addresses appear on screen, in the report, in the JSON file, in the PDF, in the progress file, or in the on-disk cache. It needs no key and no internet connection, and takes a dozen or so seconds:

```bash
python3 tests/test_kanarek.py -v
```

At the end the test lists the fields where a first and last name can still pass through: only names and subjects you typed yourself in the panel (list, automation, form and store names, email subjects) — no program can tell that "Jan Kowalski" is a person and not a product name. Test code: [tests/test_kanarek.py](tests/test_kanarek.py).

## Install in Claude Code

0. Install [Claude Code](https://claude.com/claude-code) and sign in with your Claude account on first run: type `claude` in a terminal, then `/login`.
1. In Claude Code, type:

```
/plugin marketplace add Autilos/audyt-mailingu
/plugin install audyt-mailingu@audyt-mailingu
```

2. Type **„zrób audyt mailingu”** ("run an email audit") — the skill walks you through it step by step: which platform, where to get the key, how to save it without pasting it into the chat and **without closing Claude Code**, a connection test, the run itself, and a reminder to delete the key.

**Saving the key without closing Claude Code:** open a second terminal window or tab and paste (Mac / Linux):

```bash
mkdir -p ~/.config/audyt-mailingu && (umask 077; read -rs K && printf %s "$K" > ~/.config/audyt-mailingu/getresponse.key && echo "Klucz zapisany (${#K} znaków)"; unset K)
```

Paste the key (nothing will be displayed) and press Enter — you'll see „Klucz zapisany (N znaków)” ("Key saved (N characters)"). Go back to Claude Code and type „gotowe” ("done"). For MailerLite the file is called `mailerlite.key`. After the audit, delete the file: `rm ~/.config/audyt-mailingu/getresponse.key`.

**Large account?** By default the audit covers 30 days (90 on request), runs in the background and shows progress (the `audyt-getresponse.postep.txt` file). If it gets interrupted, a rerun doesn't start from scratch — it remembers the API responses it already fetched for 12 hours (in a temporary directory, without personal data).

## No-AI mode

**Run the script yourself in a terminal. The PDF and MD report are created on your computer, and nothing from your account reaches any AI model.** You don't need Claude Code for this — just Python 3.8+ (no extra packages) and a copy of the repository (**Code → Download ZIP** on GitHub, or `git clone https://github.com/Autilos/audyt-mailingu`).

Mac / Linux, in the repository directory:

```bash
# GetResponse: paste the key after Enter (nothing is displayed and it doesn't stay in your shell history)
read -rs GETRESPONSE_API_KEY && export GETRESPONSE_API_KEY
python3 skills/audyt-getresponse/scripts/audyt_getresponse.py --raport audyt-getresponse.md
python3 skills/audyt-getresponse/scripts/raport_pdf.py audyt-getresponse.md

# MailerLite
read -rs MAILERLITE_API_KEY && export MAILERLITE_API_KEY
python3 skills/audyt-mailerlite/scripts/audyt_mailerlite.py --raport audyt-mailerlite.md
python3 skills/audyt-mailerlite/scripts/raport_pdf.py audyt-mailerlite.md
```

Windows (PowerShell 7):

```powershell
$env:GETRESPONSE_API_KEY = Read-Host -MaskInput "API key"
python skills/audyt-getresponse/scripts/audyt_getresponse.py --raport audyt-getresponse.md
python skills/audyt-getresponse/scripts/raport_pdf.py audyt-getresponse.md
```

The script connects only to the official GetResponse or MailerLite API. You read the report (`.md` and `.pdf`) yourself. The PDF needs Chrome, Chromium or Edge (without them you get an HTML file to print); the browser runs invisibly in the background and offline. Try it first without a key: add `--pokaz`.

Useful options: 30 days by default, `--dni 90` for a longer period; progress in `<report>.postep.txt`; `--test-polaczenia` checks the key with a single request; comparison with store figures (GetResponse): `--przychod-sklepu 12345 --zamowienia-sklepu 67`. Delete the key in the panel after the audit.

Tests: `python3 -m unittest discover -s tests -v`.

## For contributors

Before changing the code, the report or a SKILL.md, read [docs/CONCEPTS.md](docs/CONCEPTS.md) (in Polish) — a glossary of terms (what "the automation works" means, "order without a contact", "opens without bots", the allowlist of API paths). Tests: `python3 -m unittest discover -s tests -v`.

## Author

Wojciech Nowak — [marketingkrokpokroku.pl](https://marketingkrokpokroku.pl). Changes: [CHANGELOG.md](CHANGELOG.md) (in Polish).

## Found it useful?

Leave a [star on GitHub](https://github.com/Autilos/audyt-mailingu) or a short [review](https://github.com/Autilos/audyt-mailingu/discussions/3) — without any data from your account.

## Want a full audit or help implementing the fixes?

This is a basic audit. For a full audit (with a manual walk-through of automations, the purchase path and sales from email) or help implementing the fixes, get in touch via the [contact form](https://marketingkrokpokroku.pl/audyt-mailingu/?zrodlo=github#kontakt) or at wnowak@autilo.eu (Wojciech Nowak). More about the tool: [marketingkrokpokroku.pl/audyt-mailingu](https://marketingkrokpokroku.pl/audyt-mailingu/).
