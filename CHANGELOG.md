# Changelog

All notable changes to FST - Finance Management are listed here, newest first.

---

## v2.5.0 - Sales & purchase list

**Added**
- Sales & Purchase List page showing every saved entry, with no date limit by default.
- Invoice view and line-item view.
- Filters for dates (today, this month, all time, or a custom range), status, and search by invoice, party or product.
- Totals for the current filter. Double-click a row to open it.
- Share any entry on WhatsApp from the list, and export the list to CSV.

---

## v2.4.0 - WhatsApp sharing

**Added**
- Share sales invoices, purchase invoices and quotations as PNG images.
- Share window with a contact picker, image preview, and editable number and message.
- "Copy image and open WhatsApp" copies the image and opens the chat.
- Phone numbers are converted to international format. The country code is set in Settings (default 92).
- Save the image to a file if copying is not possible.

**Requires:** Pillow (`pip install -r requirements.txt`).

---

## v2.3.0 - Ledger and financial reports

**Added**
- Double-entry ledger. Sales, purchases and payments post automatically.
- Quick entries for expenses, owner capital, drawings, other income, and cash-to-bank transfers.
- Accounts list with balances, a journal with entry details, and account and customer/supplier statements.
- Financial reports: profit & loss, balance sheet, trial balance, sales and purchase registers, receivables and payables aging, stock valuation, tax summary, and expense breakdown.
- Reports export to CSV or printable text.

**Fixed**
- Payments taken when an invoice is saved are now dated the invoice date, so monthly statements are correct.

---

## v2.2.0 - Security and sign-in

**Added**
- Passwords are now 4-digit PINs.
- "Keep me signed in" logs you in automatically on the next launch.
- Forgot password, using a recovery question chosen at sign-up.
- Recovery questions can be added later in Settings for accounts created before this version.

**Changed**
- PIN fields accept digits only, up to four characters.

---

## v2.1.0 - Date of entry

**Added**
- Date-of-entry field on sales and purchase invoices, so past transactions can be recorded on the correct day.
- Invoice dates drive the ledger, history, dashboard and reports.
- Product descriptions on every invoice line, copied from the product's description in Inventory.

---

## v2.0.0 - Redesign

**Changed**
- Navigation moved to a left sidebar.
- New font and layout, with stat cards and a 7-day sales chart on the dashboard.
- Saved customers and suppliers can be picked on any invoice, with a type-to-search box.
- Partial payments on invoices, with payment status and balances due.
- Invoice details window, with receipts and invoice deletion. Deleting an invoice restores its stock.
- Discounts and tax on invoices, with a default tax rate in Settings.
- Keyboard shortcuts (`Ctrl+1` to `Ctrl+9`, `Ctrl+S`, `Ctrl+N`, `Ctrl+F`).
- Backups from Settings.

**Note:** Version 2 uses a new database file. Data from v1 is not carried over automatically.

---

## v1.0.0 - Initial release

**Added**
- Login and sign-up screen, with a "Remember password" option.
- Sales and purchase invoices with several products per invoice.
- Customer and supplier lists with contact details.
- Inventory with stock levels and low-stock items.
- Quotation maker.
- Light and dark themes.
- CSV import and export on every list, with downloadable sample sheets.
