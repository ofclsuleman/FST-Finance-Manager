# Changelog

All notable changes to FST - Finance Management are listed here, newest first.

---

## v2.8.0 - Customer ledger layout

**Changed**
- **Customer details** is now a ledger, in the columns: Date | Invoice no | Product | Description | Qty | Amount | Total | Received.
  - Each invoice product is a row on its invoice date. The invoice total is shown on its first row.
  - Each payment is its own row on the date it was received, under Received. Payments are no longer nested inside the invoice.
  - Rows are in date order, and a Totals row ends the ledger.
- The PDF is landscape, so all eight columns fit. The business name is printed large at the top.
- The summary shows the opening balance (owed before the period), total billed in the period, received in the period, and the remaining balance at the end of the period.
- The CSV has the same columns and the same summary at the top.

**Fixed**
- The period totals now start from the opening balance, so "remaining" is correct for any date range, not only all time.

---

## Period totals on reports

**Added**
- A totals strip at the top of the Reports page, for the date range you have chosen. It shows, for sales and for purchases: the total billed, the amount paid so far, and the amount still remaining, plus the number of invoices.
- The strip updates with the period, so this month, this year or all time each show their own totals.

---

## Customer details CSV and PDF

**Added**
- **Customer details (CSV)** and **Print / save PDF** in the Ledger, for the selected customer. Both list every invoice in the chosen period with:
  - the invoice number, date and payment method, with total, paid and due
  - every product line: product name, description, quantity, unit price and amount
  - every payment: date, method, note and amount
  - the total billed, total paid, balance due for the period and the outstanding balance now
- An invoice shows in the details if it was dated in the period or received a payment in it, so an old invoice paid this month is included.
- The PDF is A4, with page numbers, and needs no extra software. Use your PDF viewer to print it.

**Changed**
- Receipts and payments in the ledger now show the payment method in their description, for example "Receipt against INV-... (JazzCash)".

**Why the old CSV looked empty**
- The statement CSV only listed invoice totals and receipts. It did not include products, descriptions or payment methods. Use Customer details for those.

## Ledger export

**Added**
- **Export ledger to CSV** from the Ledger's customer or supplier view, in two ways:
  - **Export this statement**: one party, with a header block (business, name, phone, period, currency), the opening balance, every movement with its invoice or payment reference, description, debit, credit and running balance, and the closing balance.
  - **Export all customers** (or suppliers): every party that has a balance or movement in the chosen period, in one file. Each row names its party, so it can be filtered, and the file ends with the total closing balance.
- Files are saved with UTF-8 encoding so they open correctly in Excel.

## Customer payments, one Parties page, profile picture

**Added**
- **Receive payment** for customers. Pick a customer on the Customers page (or in the Ledger), click Receive payment, enter the amount and the date it was received. No items are added. The amount is applied to the oldest unpaid invoices first, and the customer's debt goes down by the same amount. Each payment is dated on the day it was received and posted to the ledger. Overpayments are refused.
- **Customers & Suppliers** are now one page with two tabs at the top, instead of two sidebar entries.
- **Profile picture** in Settings → Profile picture. The picture is cropped to a square, stored in the database, and shown in the sidebar. Remove it at any time.
- **Calendar picker** on every date field (Ledger, Sales & Purchase List, Reports, invoice date of entry, quotation valid-until, and Receive payment). You can still type the date as YYYY-MM-DD.
- **Mouse wheel** changes the selection in the customer, supplier and product boxes. Wheel up goes to the previous option, wheel down to the next.
- **Export statement** in the Ledger saves the customer or supplier statement as a CSV file (opens in Excel), with the opening and closing balances.
- **Record an expense** button on the Expense breakdown report. It asks for the expense account, the account paid from (Cash or Bank & mobile wallets), the amount, the date and a description, and posts a balanced ledger entry.

**Changed**
- **Ledger** now shows customer and supplier ledgers only. The Accounts & balances, Journal, Account statement and Quick entry tabs are removed from the menu.
- Report period fields use the calendar picker.
- The Expense breakdown note now points to the Record an expense button.
- About Us shows the correct version number (it showed 2.0.0 before).

**Known gaps**
- Owner capital, owner drawings and cash-to-bank transfer entries have no button in this version. Tell us where you want them and they will be added.
- The journal view is not in the menu, so manual entries can't be reviewed or deleted from the app until it is added back.

---

## v2.6.0 - Customer ledger, invoice images and picker fixes

**Added**
- Customer and supplier statements in the Ledger open as soon as you pick a name. Typed names are matched too.
- Ledger period buttons: This month, This year and All time. Leave a date box blank for no limit.
- Invoice and quotation images can be copied to the clipboard with one click, then pasted anywhere with Ctrl+V (⌘V on a Mac).
- The image window includes a caption text with its own Copy text button, and a Save image file option.
- JazzCash payment method for sales, purchases and payments. Money goes to the Bank & mobile wallets account.
- Edit a saved sale or purchase from the Sales or Purchase history, the Sales & Purchase List, or the invoice details window. Saving replaces the invoice, keeps its number, and adjusts stock, the ledger and payments.
- Delete a sale or purchase directly from the lists. Stock and ledger entries are reversed.

**Changed**
- "Share on WhatsApp" is replaced by "Copy invoice image" (and "Copy quotation image") on Sales, Purchase, the Sales & Purchase List, the invoice details window and Quotations.
- The contact picker shows up to 500 customers or suppliers, up from 25.

**Fixed**
- Customers did not appear in the Sales, Quotation or Ledger pickers. Opening the list searched for the placeholder or the chosen name, so nothing matched. It now shows the full list.
- Invoice and quotation images showed the phone number in the customer name as well as the phone line. The name is now saved and printed without the phone number. Existing invoices are cleaned up automatically on first start.

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
