# FST - Finance Management

**Version 3.0.0**

A desktop finance app for small businesses. It handles sales and purchase invoices, customers and suppliers, inventory, quotations, customer and supplier ledgers, financial reports, and copying invoice images to share on WhatsApp.

Built with Python and Tkinter, with SQLite for storage. The app runs with no third-party packages, apart from Pillow for image sharing.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Sales and purchases**
  - Multi-product invoices, with a description on each line.
  - Pick a saved customer or supplier, or sell as a walk-in.
  - Discounts, tax, partial payments and a payment history.
  - Set a date of entry for backdated invoices.
  - Credit sales, receipts (text files), and an invoice details view.
- **Sales & purchase list:** every saved entry, by invoice or by product line, with date, status and search filters.
- **Customers and suppliers:** one page with two tabs. Saved contacts with balances due, and a **Receive payment** button for customers.
  - Receive a lump-sum payment on any date. It is applied to the oldest unpaid invoices first, and no items are added.
- **Inventory:** SKU, category, cost and sale price, reorder levels, low-stock filter, and stock adjustments. Selling items at zero stock is allowed, and deleting an invoice restores its stock.
- **Quotations:** create quotes, copy them as images, track their status, and convert accepted quotes into sales.
- **Ledger:** customer and supplier statements for any period, with period buttons (This month, This year, All time). Export a statement, or every customer or supplier, to CSV for Excel. For a customer, **Customer details** lists every invoice with its products, descriptions and payments, as CSV or PDF. Export any statement to CSV for Excel. Sales, purchases and payments post to a double-entry journal automatically.
- **Financial reports:** profit & loss, balance sheet, trial balance, sales and purchase registers, receivables and payables aging, stock valuation, tax summary and expense breakdown. Record an expense from the expense report. Export to CSV or printable text.
- **Invoice images:** copy any invoice or quotation as a PNG image to the clipboard, then paste it into WhatsApp. See [Sharing on WhatsApp](#sharing-on-whatsapp).
- **CSV import and export** for contacts, products and invoice lines, with sample sheets.
- **Security:** 4-digit password, "Keep me signed in" auto-login, Forgot password through a recovery question, and salted PBKDF2 password hashing.
- **Profile picture:** choose one in Settings. It is shown in the sidebar.
- **Backups:** one click in Settings.
- **Easy selection:** calendar picker on every date field, and the mouse wheel steps through customers, suppliers and products.
- **Four colour themes** (Midnight Indigo, Clean Blue, Warm Sand, Emerald Pro), chosen in Settings, and keyboard shortcuts (`Ctrl+1`…`Ctrl+9`, `Ctrl+S`, `Ctrl+N`, `Ctrl+F`).

## Requirements

- Python 3.8 or newer, with Tkinter.
  - Windows and macOS: included in the python.org installer.
  - Debian/Ubuntu: `sudo apt install python3-tk`
- Pillow, for sharing images: `pip install -r requirements.txt`

## Quick start

```bash
git clone https://github.com/<your-username>/fst-finance.git
cd fst-finance
pip install -r requirements.txt
python fst_finance.py
```

On Windows you can double-click `run_fst.bat`. On macOS or Linux, run `./run_fst.sh`.

The first time, choose **Create a new account**. Enter a 4-digit password and choose a recovery question. The recovery question is what lets you reset the password later.

## Sharing on WhatsApp

Open an invoice or quotation and press **Copy invoice image** (or **Copy quotation image**). A window opens with the document as an image.

1. Press **Copy image** in that window. The image goes to the clipboard.
2. Open WhatsApp, choose the chat, press Ctrl+V (⌘V on macOS) and then Send.

The window also has **Copy text** for the caption, and **Save image file** if you want to attach the PNG yourself.

WhatsApp doesn't let desktop programs attach files to a chosen contact automatically, so the paste step is needed.

## Where your data is stored

All data is kept locally in a folder in your user profile:

| OS | Location |
|---|---|
| Windows | `C:\Users\<name>\.fst_finance\` |
| macOS / Linux | `~/.fst_finance/` |

| File or folder | Contents |
|---|---|
| `fst_finance_v2.db` | The database: accounts, invoices, contacts, products, ledger, profile picture |
| `session.json` | Auto-login token (no password is stored) |
| `backups/` | Database copies made from Settings |
| `shares/` | Invoice and quotation images |

Settings → **Open data folder** opens this folder. Back up the database regularly, for example by copying `backups/` to a USB drive or cloud storage.

## Building a standalone app

End users don't need Python if you build an executable:

```bash
pip install pyinstaller
build_exe.bat      # Windows: dist\FST - Finance Management.exe
./build_exe.sh     # macOS / Linux
```

## Running the tests

```bash
python -m unittest discover -s tests -v
```

The tests cover the accounting logic, invoices, stock, customer payments, expenses, the ledger, reports, profile pictures, auth and sharing. They don't need a display.

## Project structure

```
fst_finance.py          Entry point: starts the app and handles auto-login
fstapp/
  config.py             Paths, constants, colour themes
  database.py           SQLite schema, migrations, invoice and stock rules
  ledger.py             Double-entry journal, posting rules, statements
  ledger_export.py      CSV export of customer and supplier ledgers
  customer_report.py    Customer details as CSV and PDF (drawn with Pillow)
  report_engine.py      Financial report builders
  documents.py          Renders invoices and quotations as PNG images
  share.py              Phone numbers, WhatsApp links, clipboard (copy image)
  share_view.py         Image window: copy image, copy caption, save file
  photo.py              Profile picture: square crop, round display
  security.py           Password hashing, PIN rules, session tokens
  csv_io.py             CSV import and export helpers
  ui_kit.py             Reusable themed widgets
  auth_view.py          Sign-in, sign-up and Forgot password screens
  shell.py              Main window: sidebar, top bar, page switching
  pages/                One module per screen (sales, purchases, parties, ledger, reports, ...)
                        receive.py is the Receive payment dialog used by Parties and Ledger
assets/                 App icons (PNG, ICO, SVG)
tests/                  Unit tests
tools/make_icons.py     Regenerates the icons
```

## Notes and limitations

- This is not certified accounting software. Check the reports with your accountant before you rely on them for tax filings.
- Passwords are stored as salted PBKDF2-SHA256 hashes. "Keep me signed in" stores a random session token, not the password.
- The recovery answer can be used by anyone who knows it. Choose an answer that others can't guess.
- Profit in the reports uses the product's current cost price. Stock valuation is only as accurate as the stock counts you enter.
- Sharing is limited to images and the paste step described above. The WhatsApp Business API is not used.
- Owner capital, drawings and cash-to-bank transfer entries have no button in this version (see the changelog).

## Contributing

Issues and pull requests are welcome. Please run the test suite before submitting a change.

## License

Released under the [MIT License](LICENSE).
