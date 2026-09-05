# KAY POS Touch — Phase W2

Date: 2026-09-05
Status: Staff authentication implemented

W2 connects the Touch POS shell to the existing `/api/login` authentication and adds a server-authoritative Touch POS session check. An Admin account or an account with the `create_sale` permission can enter the workspace. A view-only account receives an access message and no Touch POS session is retained.

## Session behavior

- The bearer token is kept in `sessionStorage`, so it is limited to the current browser tab/app session.
- Passwords are never written to browser storage and are cleared after success, failure, expiry, and sign out.
- Page startup validates an existing token through `/api/touch-pos/session` before showing the workspace.
- A `401` response returns the user to sign-in with an expired-session message.
- Sign out calls `/api/touch-pos/logout`, revokes the current server token, clears the browser token, and hides the workspace.
- User name, role, initials, and sales-access status are displayed as plain text.

Product search and category controls continue in [Phase W3](phase_w3.md). Cart and payment remain for W4 and later. W2 performs no sale or inventory mutation.
