# Touch Settings

Open the sidebar > Settings. Manager/Admin can access shared preferences; Users requires Admin.
Each section saves only its own fields. No schema migration is required: preferences use the existing settings table, payment types use payment_types, and accounts use users with the existing password hashing format.

Sections: Appearance, Printer, Payment Types, Tax and Discount, Business and Branding, Receipt Text, Regional, Users.

- Appearance shares theme and follow_system_theme with App and applies to Touch at login and after saving.
- Printer shares receipt_printer_name, receipt_paper_size (0=80mm, 1=58mm, 2=A4), receipt_print_quality and receipt_cash_drawer_use_receipt_printer. Touch still uses the browser print dialog. Machine-specific network printer credentials are not exposed or changed.
- Tax/discount defaults and payment names refresh when opening Touch checkout. Tax is calculated after discount.
- Branding stores PNG/JPEG data URLs using the same shop_logo_image/shop_qr_code_image keys as App. Replacing/removing an image clears the old path so App restores the shared image.
- Regional saves the shared App/Lite currency and language. Touch labels currently remain English and catalog currency labels remain Ks; changing currency does not convert prices.
- Users supports add/edit/delete. A blank password on edit retains the old password. Existing endpoint permissions and self-deletion protection remain; the last active administrator cannot be demoted or disabled.

Deployment: pull main, restart the API server, refresh Touch. Restart/reopen App settings to reload shared values where needed.

Verification: isolated browser fixture for branding save and user editor; settings validation and shared-key tests; Touch checkout tax test; existing inventory, receipt, refund and stock-action checks. Production printer hardware and multi-device acceptance were not exercised.
