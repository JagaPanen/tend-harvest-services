# JagaPanen billing

## Plans

| Plan  | Optimize runs             | Notes                                         |
| ----- | ------------------------- | --------------------------------------------- |
| Guest | 5 / session               | Demo funnel (not an org plan)                 |
| Basic | 50 / calendar month       | Default on signup (`BASIC_MAX_OPTIMIZE_RUNS`) |
| Pro   | 2 000 / calendar month    | IDR 49rb/bln checkout (`PRO_MAX_OPTIMIZE_RUNS`) |

Soft banner at **80%** of the run limit; hard stop (**429**) at **100%**.

Legacy DB values `pilot` / `starter` map to **basic**; `fleet` / `enterprise` map to **pro**.

## Stub vs live Xendit

Default: `BILLING_STUB=true` (or empty `XENDIT_SECRET_KEY`).

### Checkout (org JWT)

```http
POST /api/v1/billing/checkout
Authorization: Bearer <org-token>
Content-Type: application/json

{ "plan": "pro", "activate_stub": true }
```

- `activate_stub: true` — immediately sets org plan to Pro and resets the monthly meter (stub only).
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

### Dev-only limit demo (`DEBUG=true`)

```http
POST /api/v1/billing/dev/set-usage
{ "optimize_runs_used": 50 }
```

Then `POST /optimization/run` returns **429** with an upgrade message.
