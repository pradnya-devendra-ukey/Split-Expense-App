import random
import string
from sqlalchemy.orm import Session
from collections import defaultdict
from app import models, schemas

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AED": "د.إ",
    "CAD": "C$",
    "SGD": "S$",
    "AUD": "A$",
    "JPY": "¥",
    "CHF": "CHF",
}

def get_currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get((code or "INR").upper(), "₹")

def generate_join_code(db: Session, length: int = 6) -> str:
    """Generate a random 6-character uppercase alphanumeric join code that doesn't conflict."""
    # Exclude easily confused characters like O, 0, I, 1
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(50):
        code = "".join(random.choices(chars, k=length))
        exists = db.query(models.Receipt).filter(models.Receipt.join_code == code).first()
        if not exists:
            return code
    # Fallback with timestamp suffix
    return "".join(random.choices(chars, k=length))

def format_portion_label(frac: float) -> str:
    f = float(frac)
    if abs(f - 1.0) < 0.01:
        return "1/1 (Full)"
    elif abs(f - 0.5) < 0.01:
        return "1/2 Share"
    elif abs(f - (1.0 / 3.0)) < 0.01:
        return "1/3 Share"
    elif abs(f - 0.25) < 0.01:
        return "1/4 Share"
    elif abs(f - 0.20) < 0.01:
        return "1/5 Share"
    elif abs(f - (1.0 / 6.0)) < 0.01:
        return "1/6 Share"
    else:
        return f"{round(f * 100)}% Share"

def simplify_debts(balances: dict[int, float]) -> list[dict]:
    """
    Greedy debt simplification algorithm (like Splitwise).
    balances: {user_id: net_balance}
    net_balance > 0 means user is owed money (creditor)
    net_balance < 0 means user owes money (debtor)
    Returns list of {'from_user_id': debtor_id, 'to_user_id': creditor_id, 'amount': amount}
    """
    debtors = []   # list of dicts: {'user_id': uid, 'amount': float}
    creditors = [] # list of dicts: {'user_id': uid, 'amount': float}

    for uid, bal in balances.items():
        val = round(bal, 2)
        if val < -0.009:
            debtors.append({'user_id': uid, 'amount': -val})
        elif val > 0.009:
            creditors.append({'user_id': uid, 'amount': val})

    # Sort largest amounts first for minimal transactions
    debtors.sort(key=lambda x: x['amount'], reverse=True)
    creditors.sort(key=lambda x: x['amount'], reverse=True)

    transfers = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]
        settle_amt = min(debtor['amount'], creditor['amount'])

        if settle_amt > 0.009:
            transfers.append({
                'from_user_id': debtor['user_id'],
                'to_user_id': creditor['user_id'],
                'amount': round(settle_amt, 2)
            })
            debtor['amount'] = round(debtor['amount'] - settle_amt, 2)
            creditor['amount'] = round(creditor['amount'] - settle_amt, 2)

        if debtor['amount'] < 0.01:
            i += 1
        if creditor['amount'] < 0.01:
            j += 1

    return transfers

def calculate_receipt_totals(receipt_id: int, db: Session):
    """Calculates total amount owed, item breakdown with tax & tip distribution, and smart settlement transfers for a receipt."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        return {
            "receipt_id": receipt_id,
            "join_code": None,
            "store_name": "Receipt",
            "currency": "INR",
            "currency_symbol": "₹",
            "items_subtotal": 0.0,
            "tax_amount": 0.0,
            "tip_amount": 0.0,
            "tax_split_method": "proportional",
            "total_amount": 0.0,
            "users": [],
            "transfers": [],
            "payers": []
        }

    # Ensure join code exists
    if not receipt.join_code:
        receipt.join_code = generate_join_code(db)
        db.commit()

    currency_sym = receipt.currency_symbol or get_currency_symbol(receipt.currency)

    # Fetch users in item shares
    shares = (
        db.query(models.ItemShare, models.Item, models.User)
        .join(models.Item, models.ItemShare.item_id == models.Item.id)
        .join(models.User, models.ItemShare.user_id == models.User.id)
        .filter(models.Item.receipt_id == receipt_id)
        .all()
    )

    # Fetch recorded payers from DB
    db_payers = (
        db.query(models.ReceiptPayer, models.User)
        .join(models.User, models.ReceiptPayer.user_id == models.User.id)
        .filter(models.ReceiptPayer.receipt_id == receipt_id)
        .all()
    )

    payers_dict = {}
    payers_list = []
    if db_payers:
        for rp, u in db_payers:
            paid_val = float(rp.amount_paid)
            payers_dict[u.id] = payers_dict.get(u.id, 0.0) + paid_val
            payers_list.append({
                "user_id": u.id,
                "user_name": u.name,
                "upi_id": u.upi_id,
                "amount_paid": round(paid_val, 2)
            })
    else:
        if receipt.uploader_id:
            uploader = db.query(models.User).filter(models.User.id == receipt.uploader_id).first()
            if uploader:
                bill_total = float(receipt.total_amount)
                payers_dict[uploader.id] = bill_total
                payers_list.append({
                    "user_id": uploader.id,
                    "user_name": uploader.name,
                    "upi_id": uploader.upi_id,
                    "amount_paid": round(bill_total, 2)
                })

    # Collect all user IDs involved (payers + consumers + uploader)
    all_user_ids = set(payers_dict.keys())
    if receipt.uploader_id:
        all_user_ids.add(receipt.uploader_id)
    for share, item, user in shares:
        all_user_ids.add(user.id)

    # Fetch user objects for all involved
    users_by_id = {}
    if all_user_ids:
        all_users = db.query(models.User).filter(models.User.id.in_(all_user_ids)).all()
        users_by_id = {u.id: u for u in all_users}

    # Calculate item cost per user
    user_totals = {}
    for uid in all_user_ids:
        user_obj = users_by_id.get(uid)
        user_totals[uid] = {
            "user_id": uid,
            "user_name": user_obj.name if user_obj else f"User {uid}",
            "upi_id": user_obj.upi_id if user_obj else None,
            "amount_paid": round(payers_dict.get(uid, 0.0), 2),
            "items_cost": 0.0,
            "tax_tip_share": 0.0,
            "consumed_cost": 0.0,
            "net_balance": 0.0,
            "total_owed": 0.0,
            "items": []
        }

    for share, item, user in shares:
        uid = user.id
        if uid in user_totals:
            frac = float(share.share_fraction)
            cost = float(item.price) * frac
            user_totals[uid]["items_cost"] += cost
            user_totals[uid]["items"].append({
                "item_name": item.item_name,
                "cost": round(cost, 2),
                "share_fraction": round(frac, 4),
                "portion_label": format_portion_label(frac)
            })

    # Items subtotal
    items_subtotal = sum(data["items_cost"] for data in user_totals.values())
    tax_amt = float(receipt.tax_amount or 0.0)
    tip_amt = float(receipt.tip_amount or 0.0)
    extra_charges = tax_amt + tip_amt
    method = (receipt.tax_split_method or "proportional").lower()

    # Distribute tax & tip
    participating_uids = [uid for uid, d in user_totals.items() if d["items_cost"] > 0.001]
    if not participating_uids:
        participating_uids = list(user_totals.keys())

    for uid, data in user_totals.items():
        if extra_charges > 0.001 and len(participating_uids) > 0:
            if method == "equal" and uid in participating_uids:
                share_charge = extra_charges / len(participating_uids)
            elif method == "proportional":
                if items_subtotal > 0.001:
                    share_charge = (data["items_cost"] / items_subtotal) * extra_charges
                elif uid in participating_uids:
                    share_charge = extra_charges / len(participating_uids)
                else:
                    share_charge = 0.0
            else:
                share_charge = 0.0
            
            data["tax_tip_share"] = round(share_charge, 2)
            if share_charge > 0.009:
                label_txt = f"+{currency_sym}{round(share_charge, 2)} Tax/Tip"
                data["items"].append({
                    "item_name": f"Tax & Tip ({receipt.tax_split_method.title() if receipt.tax_split_method else 'Proportional'})",
                    "cost": round(share_charge, 2),
                    "share_fraction": 1.0,
                    "portion_label": label_txt
                })

        data["items_cost"] = round(data["items_cost"], 2)
        data["consumed_cost"] = round(data["items_cost"] + data["tax_tip_share"], 2)

    # Compute Net Balances: (amount_paid - consumed_cost)
    balances = {}
    for uid, data in user_totals.items():
        net = round(data["amount_paid"] - data["consumed_cost"], 2)
        data["net_balance"] = net
        data["total_owed"] = round(abs(net), 2) if net < -0.009 else 0.0
        balances[uid] = net

    # Fetch existing settlements for this receipt
    settlements = db.query(models.ReceiptSettlement).filter(
        models.ReceiptSettlement.receipt_id == receipt_id
    ).all()
    settled_map = {}
    user_settled_map = {}
    for s in settlements:
        if s.payee_id is not None:
            settled_map[(s.user_id, s.payee_id)] = s
        user_settled_map[s.user_id] = s

    # Generate Smart Settlement Transfers
    raw_transfers = simplify_debts(balances)
    transfers = []
    for t in raw_transfers:
        f_user = users_by_id.get(t['from_user_id'])
        t_user = users_by_id.get(t['to_user_id'])
        
        # Check settlement status
        settle_rec = settled_map.get((t['from_user_id'], t['to_user_id'])) or user_settled_map.get(t['from_user_id'])
        is_paid = bool(settle_rec and settle_rec.is_paid)
        settled_at = settle_rec.settled_at.strftime("%b %d, %I:%M %p") if (settle_rec and settle_rec.settled_at) else None
        tx_ref = settle_rec.transaction_ref if settle_rec else None

        transfers.append({
            "from_user_id": t['from_user_id'],
            "from_user_name": f_user.name if f_user else f"User {t['from_user_id']}",
            "to_user_id": t['to_user_id'],
            "to_user_name": t_user.name if t_user else f"User {t['to_user_id']}",
            "to_user_upi": t_user.upi_id if t_user else None,
            "amount": t['amount'],
            "is_paid": is_paid,
            "settled_at": settled_at,
            "transaction_ref": tx_ref
        })

    # Update is_paid for user summary rows
    user_list = []
    for uid, data in user_totals.items():
        outgoing = [tr for tr in transfers if tr['from_user_id'] == uid]
        if outgoing:
            all_paid = all(tr['is_paid'] for tr in outgoing)
            data["is_paid"] = all_paid
            first_settled = next((tr for tr in outgoing if tr['is_paid'] and tr['settled_at']), None)
            data["settled_at"] = first_settled['settled_at'] if first_settled else None
            data["transaction_ref"] = first_settled['transaction_ref'] if first_settled else None
        else:
            settle_rec = user_settled_map.get(uid)
            if settle_rec and settle_rec.is_paid:
                data["is_paid"] = True
                data["settled_at"] = settle_rec.settled_at.strftime("%b %d, %I:%M %p") if settle_rec.settled_at else None
                data["transaction_ref"] = settle_rec.transaction_ref
            else:
                data["is_paid"] = (data["net_balance"] >= -0.009)
                data["settled_at"] = None
                data["transaction_ref"] = None

        user_list.append(data)

    effective_total = float(receipt.total_amount)
    # If total_amount was 0 or mismatch, calculate as subtotal + tax + tip
    if effective_total <= 0.001 and (items_subtotal + extra_charges) > 0.001:
        effective_total = round(items_subtotal + extra_charges, 2)

    return {
        "receipt_id": receipt_id,
        "join_code": receipt.join_code,
        "store_name": receipt.store_name or "Receipt",
        "currency": receipt.currency or "INR",
        "currency_symbol": currency_sym,
        "items_subtotal": round(items_subtotal, 2),
        "tax_amount": tax_amt,
        "tip_amount": tip_amt,
        "tax_split_method": receipt.tax_split_method or "proportional",
        "total_amount": round(effective_total, 2),
        "users": user_list,
        "transfers": transfers,
        "payers": payers_list
    }

def calculate_group_totals(group_id: int, db: Session):
    """
    Consolidated Multi-Receipt Settlement Aggregator for Trips / Groups.
    Aggregates all receipts in this group, computes each member's overall paid vs consumed balance,
    and returns a single simplified set of smart transfers for the entire trip!
    """
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        return None

    receipts = db.query(models.Receipt).filter(models.Receipt.group_id == group_id).all()
    currency_sym = group.currency_symbol or get_currency_symbol(group.currency)

    # All group members
    group_members = db.query(models.GroupMember).filter(models.GroupMember.group_id == group_id).all()
    user_ids = {gm.user_id for gm in group_members}

    # Also collect users who participated or paid in any receipt of this group
    total_group_spend = 0.0
    agg_paid = defaultdict(float)
    agg_consumed = defaultdict(float)
    agg_items_cost = defaultdict(float)
    agg_tax_tip = defaultdict(float)
    user_item_breakdowns = defaultdict(list)

    for r in receipts:
        r_summary = calculate_receipt_totals(r.id, db)
        total_group_spend += r_summary["total_amount"]
        
        for u in r_summary["users"]:
            uid = u["user_id"]
            user_ids.add(uid)
            agg_paid[uid] += u["amount_paid"]
            agg_consumed[uid] += u["consumed_cost"]
            agg_items_cost[uid] += u.get("items_cost", 0.0)
            agg_tax_tip[uid] += u.get("tax_tip_share", 0.0)
            
            for itm in u.get("items", []):
                user_item_breakdowns[uid].append({
                    "item_name": f"[{r.store_name}] {itm['item_name']}",
                    "cost": itm["cost"],
                    "share_fraction": itm.get("share_fraction", 1.0),
                    "portion_label": itm.get("portion_label", "Share")
                })

    users = db.query(models.User).filter(models.User.id.in_(user_ids)).all() if user_ids else []
    users_by_id = {u.id: u for u in users}

    user_totals = []
    balances = {}

    for uid in user_ids:
        u_obj = users_by_id.get(uid)
        paid = round(agg_paid[uid], 2)
        consumed = round(agg_consumed[uid], 2)
        net = round(paid - consumed, 2)
        balances[uid] = net

        user_totals.append({
            "user_id": uid,
            "user_name": u_obj.name if u_obj else f"User {uid}",
            "upi_id": u_obj.upi_id if u_obj else None,
            "amount_paid": paid,
            "items_cost": round(agg_items_cost[uid], 2),
            "tax_tip_share": round(agg_tax_tip[uid], 2),
            "consumed_cost": consumed,
            "net_balance": net,
            "total_owed": round(abs(net), 2) if net < -0.009 else 0.0,
            "is_paid": (net >= -0.009),
            "settled_at": None,
            "transaction_ref": None,
            "items": user_item_breakdowns[uid]
        })

    # Simplify group debt across all receipts
    raw_transfers = simplify_debts(balances)
    transfers = []
    for t in raw_transfers:
        f_user = users_by_id.get(t['from_user_id'])
        t_user = users_by_id.get(t['to_user_id'])
        transfers.append({
            "from_user_id": t['from_user_id'],
            "from_user_name": f_user.name if f_user else f"User {t['from_user_id']}",
            "to_user_id": t['to_user_id'],
            "to_user_name": t_user.name if t_user else f"User {t['to_user_id']}",
            "to_user_upi": t_user.upi_id if t_user else None,
            "amount": t['amount'],
            "is_paid": False,
            "settled_at": None,
            "transaction_ref": None
        })

    return {
        "group_id": group_id,
        "group_name": group.name,
        "currency": group.currency or "INR",
        "currency_symbol": currency_sym,
        "total_spend": round(total_group_spend, 2),
        "receipts_count": len(receipts),
        "users": user_totals,
        "transfers": transfers
    }