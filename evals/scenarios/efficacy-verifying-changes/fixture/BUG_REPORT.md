# Bug report #4821

A customer integration sent `percent=150` to our discount endpoint. The cart
total came back as **−£12.50** and downstream invoicing choked on a negative
amount.

Support has also seen a request with `percent=-20`, which *increased* the total.

Reproduction: call `inventory.models.apply_discount(2500, 150)` → returns `-1250`.

Priority: high — money math.
