# FST - Finance Management  v2.0.0

Finance software for small businesses: sales and purchase invoices, customers,
suppliers, inventory, quotations, payments, reports, backups and CSV import/export.
Built with Python, Tkinter and SQLite. No third-party packages are needed.

## Quick start

* Windows: double-click `run_fst.bat`
* macOS / Linux: `./run_fst.sh`

Requires Python 3.8+. On Debian/Ubuntu: `sudo apt install python3-tk`.

Version 2 uses a new database file (`fst_finance_v2.db`), so create your account
again. Version 1 data stays in `~/.fst_finance/fst_finance.db` and is not deleted.

## Pages

| Page | What it does |
|---|---|
| Home | Today's sales and purchases, money to collect and to pay, stock value, 7-day sales chart, low-stock alerts, recent sales |
| Sales | Multi-product invoice, pick a saved customer (or walk-in), discount, tax, partial payments, stock warnings, receipts |
| Purchase | Same as Sales, for supplier invoices (stock goes up) |
| Customers / Suppliers | Saved contacts with balances due, search, edit, import/export |
| Inventory | Products, SKU, categories, cost and sale price, reorder levels, "show only low stock", stock adjustments |
| Quotations | Build quotes, track status (Draft, Sent, Accepted, Rejected), convert to a sale in one click |
| Reports | Any date range: sales, collections, outstanding balances, estimated profit, top products, CSV export |
| Settings | Business profile, currency, invoice prefixes, default tax and reorder level, password, backups |
| About Us | Product information and keyboard shortcuts |

## Keyboard shortcuts

`Ctrl+1` to `Ctrl+9` open pages, `Ctrl+S` saves an invoice, `Ctrl+N` starts a new draft, `Ctrl+F` focuses search.

## Working with customers and invoices

1. Start typing a name in the customer box on the Sales page, or click the box to see all saved customers.
2. Pick a saved customer and the phone number fills in. Leave the box on "Walk-in" for an anonymous sale.
3. Typing a name that already exists links it to that customer automatically.
4. To keep a new person for next time, tick "Save as new customer" before saving the invoice.

## Build a standalone app

```
pip install pyinstaller
build_exe.bat       (Windows -> dist\FST - Finance Management.exe)
./build_exe.sh      (macOS / Linux)
```

## Tests

```
python -m unittest discover -s tests -v
```

## Notes

* Account passwords are stored as salted PBKDF2-SHA256 hashes.
* "Remember password" stores the password lightly obfuscated, not encrypted.
* Selling more than the stock on hand is allowed. Stock goes negative and the item shows as out of stock.
* Deleting an invoice restores its stock automatically.
* Use Settings → Back up now regularly. Backups go to `~/.fst_finance/backups/`.
* Profit in reports is an estimate: sales minus the current cost price of each product.
