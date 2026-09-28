from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models, schemas

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

def calculate_receipt_totals(receipt_id: int, db: Session):
    """Calculates total amount owed and item breakdown for a specific receipt."""
    shares = (
        db.query(models.ItemShare, models.Item, models.User)
        .join(models.Item, models.ItemShare.item_id == models.Item.id)
        .join(models.User, models.ItemShare.user_id == models.User.id)
        .filter(models.Item.receipt_id == receipt_id)
        .all()
    )

    user_totals = {}
    for share, item, user in shares:
        if user.id not in user_totals:
            user_totals[user.id] = {
                "user_id": user.id,
                "user_name": user.name,
                "total_owed": 0.0,
                "items": []
            }
        
        frac = float(share.share_fraction)
        cost = float(item.price) * frac
        user_totals[user.id]["total_owed"] += cost
        user_totals[user.id]["items"].append({
            "item_name": item.item_name,
            "cost": round(cost, 2),
            "share_fraction": round(frac, 4),
            "portion_label": format_portion_label(frac)
        })

    result = []
    for uid, data in user_totals.items():
        data["total_owed"] = round(data["total_owed"], 2)
        result.append(schemas.UserTotalOwed(**data))
    
    return result