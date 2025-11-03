# FitBot

Python script to automate your session bookings in [aimharder.com](http://aimharder.com) platform

## Usage

Having docker installed you only need to do the following command:

```bash
docker run \
  -e email=YOUR_EMAIL@example.com \
  -e password=YOUR_PASSWORD \
  -e booking-goals={'"0":{"time":"1815","name":"CLASS_KEYWORD"}'} \
  -e box-name=YOUR_BOX_SUBDOMAIN \
  -e box-id=YOUR_BOX_ID \
  -e days-in-advance=3 pablobuenaposada/fitbot
````
Explanation about the fields:

`email`: self-explanatory

`password`: self-explanatory

`booking_goals`: expects a json where as keys you would use the day of the week as integer from 0 to 6 (Monday to Friday) and the value should be the time (HHMM) of the class and the name of the class or part of it.
Unfortunately this structure needs to be crazy escaped, but here's an example:

Mondays at 18:15 class name should contain CLASS_KEYWORD
Wednesdays at 18:15 class name should contain CLASS_KEYWORD
```python
{
  "0": {"time":"1815", "name":"CLASS_KEYWORD"},
  "2": {"time":"1815", "name":"CLASS_KEYWORD"}
}
```
which should be sent in this form:
```sh
{'\"0\":{\"time\":\"1815\"\,\"name\":\"CLASS_KEYWORD\"}\,\"2\":{\"time\":\"1815\"\,\"name\":\"CLASS_KEYWORD\"}'}
```

`box-name`: this is the sub-domain you will find in the url when accessing the booking list from a browser, something like _https://**yourboxsubdomain**.aimharder.com/schedule_

`box-id`: it's always the same one for your gym, you can find it inspecting the request made while booking a class from the browser:

<img src="https://raw.github.com/pablobuenaposada/fitbot/master/inspect.png" data-canonical-src="https://raw.github.com/pablobuenaposada/fitbot/master/inspect.png" height="300" />

`days-in-advance`: this is how many days in advance the script should try to book classes from, so for example, if this script is being run on a Monday and this field is set to 3 it's going to try book Thursday class from `booking_goals`

`family-id`: Optional. This is the id for the person who wants to book a class in case the account has more than one member. 
The value for this parameter can be found by inspecting the requests with the browser, as with the field `box-id`.

`proxy`: Optional. If you want to use a proxy, you can set it with the format `socks5://ip:port`.

## 🚨 Proxy note 🚨
It appears that AimHarder has started blocking connections by returning a 403 error based on the IP address location. If you are running this script from outside Spain, you may encounter these errors, which is why the proxy argument has been added.

The United States seems to be heavily blocked (possibly only Azure IPs), so running this script from GitHub Actions will likely fail without a proxy. While this is not confirmed, it seems AimHarder doesn't like the use of automated scripts, especially when run for free via GitHub Actions 😀. If you choose this approach, ensure you use a proxy that is not blocked by AimHarder.

**Note:** Use free proxies at your own risk, as your credentials will be transmitted through them. Additionally avoid sharing the proxy you are using in here since AimHarder may block it.

## I'm a cheapo, can I run this without using my own infrastructure for free?
Yes, you can! By using GitHub Actions, you can run this script without needing your own infrastructure. It can also be configured to run automatically on a schedule. For details about potential connection blocks and proxy usage, refer to the previous section.

You can find the automated booking workflow added in this repo at [`.github/workflows/book-7am.yml`](.github/workflows/book-7am.yml).

Clone this repo, get a proxy (https://www.freeproxy.world/), add your secrets, edit the file to your needs and it should be ready to go.

Enjoy!

## Automated 7AM (Mon-Fri) Booking Workflow

If you want to automatically book the 7:00 AM class Monday through Friday, a workflow file has been added at: `.github/workflows/book-7am.yml`.

### How it works
AimHarder allows booking 36 hours before class time. To book a class at 07:00 on a given weekday, the workflow runs at roughly 19:05 (local) two days prior (≈ 36h+). The schedule uses UTC cron expressions; adjust if your box is in a different timezone.

| Target Class | Runs (UTC) | Days in advance value |
|--------------|-----------|-----------------------|
| Monday 07:00 | Saturday 17:05 | 2 |
| Tuesday 07:00 | Sunday 17:05 | 2 |
| Wednesday 07:00 | Monday 17:05 | 2 |
| Thursday 07:00 | Tuesday 17:05 | 2 |
| Friday 07:00 | Wednesday 17:05 | 2 |

### Required Repository Secrets
Add these in your GitHub repo settings under Settings > Secrets and variables > Actions:

| Secret Name | Description |
|-------------|-------------|
| `EMAIL` | Your AimHarder account email (also used for NordVPN login) |
| `PASSWORD` | Your AimHarder account password |
| `BOX_NAME` | Sub-domain of your box (e.g. `yourboxsubdomain`) |
| `BOX_ID` | Numeric box ID |
| `NORD_PWD` | Your NordVPN password |
| `NORD_COUNTRY` | NordVPN country code (e.g. `es` for Spain) |
| `FAMILY_ID` | (Optional) Member ID if booking for a family member |

### Booking Goals JSON
The workflow sets `BOOKING_GOALS` to cover Monday (`0`) through Friday (`4`) at 07:00. Replace `CrossFit` with a distinctive part of the class name used at your box (e.g. `WOD`, `OPEN BOX`, etc.).

Example value used in the workflow:
```
{"0":{"time":"0700","name":"CrossFit"},"1":{"time":"0700","name":"CrossFit"},"2":{"time":"0700","name":"CrossFit"},"3":{"time":"0700","name":"CrossFit"},"4":{"time":"0700","name":"CrossFit"}}
```

### Manual Trigger
You can also trigger it manually from the Actions tab (workflow_dispatch) to test credentials or booking goals.

### Adjusting Timezone
If your box is not in Europe/Madrid timezone or daylight saving changes affect success, edit the cron entries in `.github/workflows/book-7am.yml` to reflect the correct UTC time corresponding to ~36h before the class.

### Logs & Troubleshooting
Check the workflow run logs for messages like:
- `Class already booked. Nothing to do` – A prior booking exists.
- `Too soon to book the class` – Cron may be firing before the booking window; push cron later or reduce `DAYS_IN_ADVANCE`.
- `No credit available` – Renew or purchase credits.
- `Box is closed` – No classes were returned for that date.

If repeated 403 errors appear, add a valid Spain-based proxy via the `PROXY` secret.

## NordVPN-Only Setup (Recommended for Spain IP)
If you prefer not to manage a static proxy and only want a Spain IP via NordVPN, set these GitHub Actions secrets (never commit them to the repo):

**Required Secrets:**
```
EMAIL=<your aimharder and nordvpn email>
PASSWORD=<your aimharder password>
BOX_NAME=<your box subdomain>
BOX_ID=<your box numeric id>
NORD_PWD=<your nordvpn password>
NORD_COUNTRY=es
```

**Note:** The workflow reuses your `EMAIL` secret for both AimHarder login and NordVPN authentication. If your NordVPN account uses a different email, you'll need to adjust the workflow file.

Then ensure the workflow `book-7am.yml` has the NordVPN section enabled (already included). The workflow will:
1. Connect to NordVPN using the provided country code (via `NORD_COUNTRY` secret).
2. Export a SOCKS5 proxy at `socks5://127.0.0.1:1080`.
3. Pass that proxy to the booking script automatically.

If you want to switch the exit node (e.g. Portugal) just change `NORD_COUNTRY=pt` in repository secrets—no code changes required.

### NordVPN Troubleshooting
- Connection timeout: Increase loop iterations in the workflow (change `{1..30}` to `{1..45}`).
- Wrong credentials: Logs will never show `connected`; re-check username/password.
- Country overloaded: Try a neighboring country (`fr`, `pt`) and see if AimHarder still allows booking.

## Privacy & Security Guidelines
To avoid leaking personal data or credentials:
1. Do NOT commit real emails, passwords, box IDs, or family member IDs—use GitHub Actions secrets.
2. Replace concrete class names with generic keywords (e.g., `CLASS_KEYWORD`, `WOD`) when sharing examples.
3. Redact screenshots before publishing (blur names, IDs, emails). The sample image is illustrative only.
4. Never publish proxy endpoints you actively use; they can get blocked or abused.
5. Rotate credentials periodically and revoke secrets if you suspect exposure.
6. Use least-privilege accounts—avoid using an owner account if a booking-only account exists.
7. Enable 2FA on AimHarder; store secrets only in the Actions settings, not in code.
8. Consider adding audit logging (e.g., append booking confirmations to an artifact) without sensitive data.

