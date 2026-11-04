# FST - Finance Management

A desktop finance app for small businesses. It handles sales and purchase invoices, customers and suppliers, inventory, quotations, a double-entry ledger, financial reports, and sharing invoices on WhatsApp.

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
- **Customers and suppliers:** saved contacts with balances due, and a statement for each.
- **Inventory:** SKU, category, cost and sale price, reorder levels, low-stock filter, and stock adjustments. Selling items at zero stock is allowed, and deleting an invoice restores its stock.
- **Quotations:** create quotes, track their status, and convert accepted quotes into sales.
- **Double-entry ledger:** sales, purchases and payments post automatically. Quick entries cover expenses, owner capital, drawings, other income and cash-to-bank transfers. Includes a journal, account statements and a trial balance.
- **Financial reports:** profit & loss, balance sheet, trial balance, sales and purchase registers, receivables and payables aging, stock valuation, tax summary and expense breakdown. Export to CSV or printable text.
- **WhatsApp sharing:** send an invoice or quotation as a PNG image. See [Sharing on WhatsApp](#sharing-on-whatsapp).
- **CSV import and export** for contacts, products and invoice lines, with sample sheets.
- **Security:** 4-digit password, "Keep me signed in" auto-login, Forgot password through a recovery question, and salted PBKDF2 password hashing.
- **Backups:** one click in Settings.
- **Light and dark themes**, keyboard shortcuts (`Ctrl+1`…`Ctrl+9`, `Ctrl+S`, `Ctrl+N`, `Ctrl+F`).

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

Open an invoice or quotation and press **Share on WhatsApp**. A window opens where you:

1. Pick a saved customer or supplier, or type a number. Local numbers such as `0300-1234567` get the country code added automatically (92 by default, changeable in Settings).
2. Press **Copy image and open WhatsApp**. The document image is copied and WhatsApp opens the chat.
3. Press Ctrl+V (⌘V on macOS) in the chat, then Send.

WhatsApp doesn't allow desktop programs to attach files to a chosen contact automatically, so the paste step is needed. The image is also saved in the data folder, so you can attach it manually if copying fails.

## Where your data is stored

All data is kept locally in a folder in your user profile:

| OS | Location |
|---|---|
| Windows | `C:\Users\<name>\.fst_finance\` |
| macOS / Linux | `~/.fst_finance/` |

| File or folder | Contents |
|---|---|
| `fst_finance_v2.db` | The database: accounts, invoices, contacts, products, ledger |
| `session.json` | Auto-login token (no password is stored) |
| `backups/` | Database copies made from Settings |
| `shares/` | Invoice and quotation images for WhatsApp |

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

The tests cover the accounting logic, invoices, stock, the ledger, reports, auth and sharing. They don't need a display.

## Project structure

```
fst_finance.py          Entry point: starts the app and handles auto-login
fstapp/
  config.py             Paths, constants, colour themes
  database.py           SQLite schema, migrations, invoice and stock rules
  ledger.py             Double-entry journal, posting rules, statements
  report_engine.py      Financial report builders
  documents.py          Renders invoices and quotations as PNG images
  share.py              Phone normalisation, WhatsApp links, clipboard
  share_view.py         WhatsApp share dialog
  security.py           Password hashing, PIN rules, session tokens
  csv_io.py             CSV import and export helpers
  ui_kit.py             Reusable themed widgets
  auth_view.py          Sign-in, sign-up and Forgot password screens
  shell.py              Main window: sidebar, top bar, page switching
  pages/                One module per screen (sales, purchases, ledger, reports, ...)
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

## Contributing

Issues and pull requests are welcome. Please run the test suite before submitting a change.

## License

Released under the [MIT License](LICENSE).
