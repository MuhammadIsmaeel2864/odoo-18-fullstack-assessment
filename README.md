# Odoo 18 Developer Assessment

Two custom addons for **Odoo 18 Community Edition**:

1. **Contact Access Control** (`contact_access_control`) — category-based contact creation and editing permissions.
2. **Front Desk Visitor Management** (`visitor_management`) — visitor registration, check-in/check-out, badge printing, and daily automatic checkout.

The addons extend Odoo through standard custom modules; no Odoo core files need to be modified.

## Requirements

- Odoo **18 Community Edition**
- Python **3.10 or newer**
- PostgreSQL **14 or newer**
- Odoo dependencies installed and configured (`base`, `contacts`, `hr`, `mail`)
- `wkhtmltopdf` available for PDF badge generation (included in the Windows installer used for development)

Development and validation environment: Odoo 18.0 (Windows), PostgreSQL 16.

## Project structure

```text
odoo-assignment/
├── contact_access_control/
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   ├── security/
│   ├── views/
│   └── tests/
├── visitor_management/
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   ├── security/
│   ├── data/
│   ├── views/
│   ├── report/
│   └── tests/
├── screenshots/
├── .gitignore
└── README.md
```

## Installation

1. Install and configure Odoo 18 Community Edition and PostgreSQL.
2. Clone this repository or copy both module folders into an Odoo custom addons directory.
3. Add the **parent directory** containing both addons to the `addons_path` setting in your Odoo configuration, for example:

   ```ini
   addons_path = C:\Program Files\Odoo 18.0.20261012\server\odoo\addons,C:\odoo-dev\odoo-assignment
   ```

   Preserve other addon paths needed by your existing Odoo installation.
4. Restart Odoo, create a new database, and enable **Developer Mode**.
5. Under **Apps**, use **Update Apps List** if needed, then install **Contact Access Control** first and **Front Desk Visitor Management** second. Dependencies may also be installed automatically by Odoo.
6. Configure users' access groups in **Settings → Users & Companies → Users**.

### Command-line installation (Windows example)

After configuring database credentials in your *local* Odoo configuration file, use an **unused** database name:

```powershell
$python = 'C:\Program Files\Odoo 18.0.20261012\python\python.exe'
$odoo = 'C:\Program Files\Odoo 18.0.20261012\server\odoo-bin'
$config = 'C:\Program Files\Odoo 18.0.20261012\server\odoo.conf'

& $python $odoo -c $config -d odoo_assessment_clean `
  -i base,contact_access_control,visitor_management `
  --without-demo=all --stop-after-init
```

Stop the running Odoo service first if it uses the same database or port. Do not commit local configuration files containing database passwords.

## Module 1: Contact Access Control

Extends `res.partner` with a required **Contact Category** selection:

- `customer`
- `vendor`
- `employee`
- `visitor`
- `general`

### Permission groups

| Group | Allowed contact category |
|---|---|
| Commercial | Customer |
| Procurement | Vendor |
| HR | Employee |
| Front Desk | Visitor |
| Contact Manager | All categories |

Implemented behaviors include category-specific creation and editing restrictions, filtered category selection, search/group-by support, and inheritance of a parent contact's category by child contacts. Restrictions are enforced server-side, including API/ORM operations, rather than only by form visibility. Users without an allowed group cannot create categorized contacts. Odoo administrators retain their normal elevated privileges.

## Module 2: Front Desk Visitor Management

### Data and workflow

- Visitor logs use automatic references such as `VIS/2026/0001`.
- Visitor must be a contact categorized as `visitor`.
- Host is selected from Odoo employees (`hr.employee`).
- Each log records purpose, check-in, check-out, state, and computed visit duration.
- States: **Draft → Checked In → Checked Out**, with **Cancel** and **Reset to Draft** actions.
- Invalid checkout timestamps and overlapping visits are rejected.
- State changes are tracked in Odoo chatter.

### Views

- **List** — all visitor logs.
- **Form** — visitor details and workflow buttons.
- **Kanban** — grouped by status.
- **Calendar** — visits displayed using check-in time.

### Security

Only **Front Desk** and **Contact Manager** have visitor-log model permissions; other business-role users must not be able to create or manage visitor logs.

### Automatic checkout

The scheduled action **Visitor Management: Daily Auto Checkout** calls:

```python
model._cron_auto_checkout()
```

The intended business cutoff is **11:59 PM Asia/Karachi**, equivalent to **18:59 UTC**. The checkout method uses the last completed local cutoff and preserves sessions that began after that cutoff if the scheduler executes late. Confirm the actual **Next Execution** time in **Settings → Technical → Scheduled Actions** after installation; scheduling accuracy depends on Odoo's scheduler running normally.

### Printable badge

Open a visitor log and choose **Print → Visitor Badge** to generate a QWeb PDF with the visitor reference, visitor name, host, purpose, and check-in time. PDF generation requires a working `wkhtmltopdf` installation.

## Automated testing

Odoo `TransactionCase` tests are in each module's `tests/` package.

| Module | Tests passed | Failures | Errors |
|---|---:|---:|---:|
| `contact_access_control` | 13 | 0 | 0 |
| `visitor_management` | 12 | 0 | 0 |
| **Total** | **25** | **0** | **0** |

**Fresh-database validation:** Both modules were installed together on `odoo_assessment_clean` on **12 October 2026**, with **exit code 0** and an Odoo test result of **`0 failed, 0 error(s) of 25 tests`**.

To repeat the installation and tests on a **new, unused database** (replace the database name), run:

```powershell
$python = 'C:\Program Files\Odoo 18.0.20261012\python\python.exe'
$odoo = 'C:\Program Files\Odoo 18.0.20261012\server\odoo-bin'
$config = 'C:\Program Files\Odoo 18.0.20261012\server\odoo.conf'

& $python $odoo -c $config -d odoo_assessment_retest `
  -i base,contact_access_control,visitor_management `
  --without-demo=all `
  --test-tags=/contact_access_control,/visitor_management `
  --stop-after-init --log-level=test
```

Expected ending test summary:

```text
0 failed, 0 error(s) of 25 tests
```

### Manual test checklist

- Assign each contact-security role and verify both allowed and denied category operations.
- Check category dropdown filtering and search/group-by behavior.
- Create a visitor contact and a host employee, then register a visit.
- Check in, check out, and verify computed duration.
- Attempt a second overlapping visit for the same visitor.
- Cancel a visit and reset it to Draft.
- Switch between list, form, kanban, and calendar views.
- Print the Visitor Badge QWeb PDF.
- Verify the scheduled action and exercise it using **test data only**; manual execution can affect eligible active visits.
- Confirm non-Front Desk / non-Contact Manager users cannot manage visitor logs.

## Screenshots

Capture and include images in the `screenshots/` directory, for example:

- `01-contact-category.png`
- `02-contact-role-permissions.png`
- `03-contact-search-groupby.png`
- `04-visitor-form.png`
- `05-visitor-kanban.png`
- `06-visitor-calendar.png`
- `07-visitor-badge.png`
- `08-scheduled-action.png`
- `09-test-results.png`

Use demo/test records in screenshots. Avoid exposing passwords, real visitor personal data, or credentials.

## Notes

- These modules were developed and tested for **Odoo 18 Community Edition**.
- A scheduled action's `nextcall` is represented internally in UTC; displayed time depends on the current user's timezone.
- Browser extensions that intercept downloads can interfere with Odoo's PDF download response even when the PDF itself generates successfully.
- Odoo configuration files, log files, caches, database backups, and private secrets are intentionally excluded from source control.
