# JagaPanen billing (P4)

## Plans

| Plan       | Optimize runs          | Notes                         |
| ---------- | ---------------------- | ----------------------------- |
| Guest      | 5 / session            | Unchanged demo funnel         |
| Pilot      | 25 (configurable)      | 14-day trial; `pilot_ends_at` |
| Starter    | 200 / calendar month   | Checkout                      |
| Fleet      | 1 000 / calendar month | Checkout                      |
| Enterprise | Unlimited              | Sales / manual                |

Soft banner at **80%** of the run limit; hard stop (**429**) at **100%** or when Pilot expires.

## Stub vs live Xendit

Default: `BILLING_STUB=true` (or empty `XENDIT_SECRET_KEY`).

### Checkout (org JWT)

```http
POST /api/v1/billing/checkout
Authorization: Bearer <org-token>
Content-Type: application/json

{ "plan": "starter", "activate_stub": true }
```

- `activate_stub: true` — immediately sets org plan to Starter/Fleet and resets the monthly meter (stub only).
- `activate_stub: false` — creates a `pending` subscription; complete with webhook:

```http
POST /api/v1/billing/webhook
Content-Type: application/json

{ "external_id": "<from checkout>", "status": "PAID" }
```

Optional header when `XENDIT_WEBHOOK_TOKEN` is set: `x-callback-token: <token>`.

### Usage

```http
GET /api/v1/billing/usage
```

### Dev-only Pilot limit demo (`DEBUG=true`)

```http
POST /api/v1/billing/dev/set-usage
{ "optimize_runs_used": 25 }
```

Then `POST /optimization/run` returns **429** with an upgrade message.

## Live Xendit

1. Set `BILLING_STUB=false` and `XENDIT_SECRET_KEY`.
2. Checkout still creates a pending `subscriptions` row (`xendit_invoice_id` placeholder).
3. Wire your Invoice create call to replace `checkout_url`, then rely on `/billing/webhook` with `status=PAID` to activate.
