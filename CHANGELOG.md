## v3.0.0

- Four colour themes: **Midnight Indigo** (dark), **Clean Blue** (light), **Warm Sand** (cream with a teal bar) and **Emerald Pro** (dark green). Choose one in Settings > Theme; the choice is saved and applies at once.
- The Light mode / Dark mode button in the top bar is replaced by the theme choice in Settings. Older "light" and "dark" settings map to Clean Blue and Midnight Indigo.
- Cards and buttons use raised edges, and input boxes look sunken, on every theme.
- Sales and Purchase pages are compact and fit the window; the saved-invoice list lives on the Sales & Purchase List page.
- Every page except Sales and Purchase scrolls on short windows, so nothing is cut off.
- Saved invoices can be edited straight after saving. Product lines on a saved invoice can be edited ("Edit selected line").
- The Edit, Open and Delete buttons on the Sales & Purchase List page stay visible.
- The database file keeps its name (fst_finance_v2.db) so your existing data carries over.

## v2.16.2

- Every page except Sales and Purchase now scrolls on short windows (for example Settings), so nothing is cut off at the bottom.

## v2.16.1

- Sales and Purchase pages are more compact: Discount and Tax sit side by side, Paid now and Payment method sit side by side, so the Clear and Receipt buttons are visible without scrolling.

## v2.16.0

- Sales and Purchase pages: the list of saved invoices below the entry form is removed, so the whole page fits the window without scrolling. Edit, Open, Delete and Copy image for saved entries are on the "Sales & Purchase List" page.
- Ctrl+F on the Sales and Purchase pages no longer does anything, because the search box moved to the list page.

## v2.15.3

- Sales and Purchase pages scroll when the window is short, so the bottom buttons and the Save button are never cut off.
- Section headings on the invoice page ("Items on this invoice", "Summary") and a taller saved-invoice list.

## v2.15.2

- Edit a product line on a saved invoice: select the line, press "Edit selected line", change qty, price or description, then "Update line".
- Fix: the Sales/Purchase page no longer runs off the bottom of the window. The saved-invoice list keeps its room, so Edit, Open and Delete stay visible.

## v2.15.1

- Fix: the Edit, Open and Delete buttons under the invoice list (Sales/Purchase page) and the Sales & Purchase List were pushed off-screen when the list was tall. The buttons now stay visible at the bottom.

## v2.15.0

- Neumorphism look in light and dark mode: one soft surface colour, raised cards and buttons, sunken input boxes.
- Fix: after saving an invoice, the saved invoice is selected in the history list, so Edit works right away.

# Changelog

All notable changes to FST - Finance Management are listed here, newest first.

---

## v2.14.0

- New layout: a dark top bar with the menu centred across it (design T3). The left sidebar is gone; the profile picture and name moved to the page header.
- Theme and logout buttons sit on the right of the top bar.

## v2.13.0 - Editable receipts, Reports hidden

**Added**
- **Edit or delete a payment** from an invoice's Payments list. Select the payment and click Edit selected payment (amount, date, method, note) or Delete selected payment. The ledger entry follows each change, and the invoice's paid amount updates.

**Changed**
- **Editing an invoice keeps its receipts.** Before, every edit removed all receipts and wrote a single receipt dated on the edit day. Now each receipt keeps its amount, method, date and note. The receipts are replaced only if you change the amount paid on purpose.
- An edit that would make the receipts total more than the new invoice total is refused, and nothing is changed.
- The **Reports** page is hidden from the navigation. Its code is kept, so it can be shown again later.

**Note**
- With Reports hidden, Record an expense is also not available from the app for now.

---

## v2.12.0 - Customer ledger: one row per invoice

**Changed**
- **Customer details (PDF and CSV)** now show one row per invoice, with the columns Date | Invoice no | Products | Total | Received | Remaining | Status.
  - Each product is a line inside its invoice row, with the product name, its description and its amount.
  - Status is Paid, Partly paid or Unpaid.
  - A Totals row ends the ledger.
- There is no separate payments table. A payment shows in the Received column of its invoice.
- The summary at the top is unchanged: opening balance, total billed in the period, received in the period, and remaining at the end.
- The CSV has one row per product. The invoice's total, received, remaining and status are on its first row.

**Fixed**
- An invoice dated before the period that received a payment in the period is now shown, so the Received total matches the summary.

---

## v2.11.0 - Customer ledger layout

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

## v2.10.0 - Period totals on reports

**Added**
- A totals strip at the top of the Reports page, for the date range you have chosen. It shows, for sales and for purchases: the total billed, the amount paid so far, and the amount still remaining, plus the number of invoices.
- The strip updates with the period, so this month, this year or all time each show their own totals.

---

## v2.9.0 - Customer details CSV and PDF

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

---

## v2.8.0 - Ledger export

**Added**
- **Export ledger to CSV** from the Ledger's customer or supplier view, in two ways:
  - **Export this statement**: one party, with a header block (business, name, phone, period, currency), the opening balance, every movement with its invoice or payment reference, description, debit, credit and running balance, and the closing balance.
  - **Export all customers** (or suppliers): every party that has a balance or movement in the chosen period, in one file. Each row names its party, so it can be filtered, and the file ends with the total closing balance.
- Files are saved with UTF-8 encoding so they open correctly in Excel.

---

## v2.7.0 - Customer payments, one Parties page, profile picture

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
