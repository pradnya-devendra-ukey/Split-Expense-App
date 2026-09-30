from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime
from app.database import get_db
from app import models, schemas
from app.services.split_service import calculate_receipt_totals

router = APIRouter(prefix="/split", tags=["Split"])

@router.get("/payers/{receipt_id}")
def get_receipt_payers(receipt_id: int, db: Session = Depends(get_db)):
    """Retrieve the list of payers who paid for this receipt."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    db_payers = (
        db.query(models.ReceiptPayer, models.User)
        .join(models.User, models.ReceiptPayer.user_id == models.User.id)
        .filter(models.ReceiptPayer.receipt_id == receipt_id)
        .all()
    )

    if db_payers:
        return [
            {
                "user_id": u.id,
                "user_name": u.name,
                "upi_id": u.upi_id,
                "amount_paid": float(rp.amount_paid)
            }
            for rp, u in db_payers
        ]
    
    # Fallback to uploader as 100% payer
    if receipt.uploader_id:
        uploader = db.query(models.User).filter(models.User.id == receipt.uploader_id).first()
        if uploader:
            return [
                {
                    "user_id": uploader.id,
                    "user_name": uploader.name,
                    "upi_id": uploader.upi_id,
                    "amount_paid": float(receipt.total_amount)
                }
            ]
    return []

@router.post("/payers")
def set_receipt_payers(payload: schemas.SetReceiptPayersRequest, db: Session = Depends(get_db)):
    """Save or update multiple payers for a receipt."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == payload.receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if not payload.payers:
        raise HTTPException(status_code=400, detail="At least one payer must be specified")

    # Clear previous payers for this receipt
    db.query(models.ReceiptPayer).filter(models.ReceiptPayer.receipt_id == payload.receipt_id).delete(synchronize_session=False)

    for p in payload.payers:
        if p.amount_paid > 0:
            db.add(models.ReceiptPayer(
                receipt_id=payload.receipt_id,
                user_id=p.user_id,
                amount_paid=p.amount_paid
            ))

    db.commit()
    return {"message": "Receipt payers updated successfully", "receipt_id": payload.receipt_id}

@router.post("/settle")
def settle_user_payment(payload: schemas.SettlementRequest, db: Session = Depends(get_db)):
    """Records or toggles a user's payment settlement for a specific receipt in the database."""
    query = db.query(models.ReceiptSettlement).filter(
        models.ReceiptSettlement.receipt_id == payload.receipt_id,
        models.ReceiptSettlement.user_id == payload.user_id
    )
    if payload.payee_id is not None:
        query = query.filter(models.ReceiptSettlement.payee_id == payload.payee_id)

    settlement = query.first()

    if settlement:
        settlement.is_paid = payload.is_paid
        if payload.amount is not None:
            settlement.amount = payload.amount
        if payload.transaction_ref:
            settlement.transaction_ref = payload.transaction_ref
        settlement.settled_at = datetime.utcnow()
    else:
        settlement = models.ReceiptSettlement(
            receipt_id=payload.receipt_id,
            user_id=payload.user_id,
            payee_id=payload.payee_id,
            is_paid=payload.is_paid,
            amount=payload.amount,
            transaction_ref=payload.transaction_ref,
            settled_at=datetime.utcnow()
        )
        db.add(settlement)

    db.commit()
    return {
        "message": "Payment settlement updated successfully",
        "receipt_id": payload.receipt_id,
        "user_id": payload.user_id,
        "payee_id": payload.payee_id,
        "is_paid": settlement.is_paid,
        "settled_at": settlement.settled_at.strftime("%b %d, %I:%M %p") if settlement.settled_at else None
    }

@router.post("/assign-shares")
def assign_item_shares(payload: schemas.ItemShareRequest, db: Session = Depends(get_db)):
    """
    Saves or updates a user's proportional share for an item without 
    forcing the entire payload to sum up to 1.0 at once.
    """
    for share in payload.shares:
        existing_share = db.query(models.ItemShare).filter(
            models.ItemShare.item_id == payload.item_id,
            models.ItemShare.user_id == share.user_id
        ).first()

        if existing_share:
            existing_share.share_fraction = share.fraction
        else:
            db_share = models.ItemShare(
                item_id=payload.item_id,
                user_id=share.user_id,
                share_fraction=share.fraction
            )
            db.add(db_share)

    db.commit()
    return {"message": "Share assigned successfully"}

@router.post("/bulk-assign")
def bulk_assign_shares(payload: schemas.BulkAssignRequest, db: Session = Depends(get_db)):
    """
    Clears old shares for the given receipt and assigns new ones.
    Fractions are automatically split equally among assigned users.
    """
    item_ids = [item.id for item in db.query(models.Item).filter(models.Item.receipt_id == payload.receipt_id).all()]
    if item_ids:
        db.query(models.ItemShare).filter(models.ItemShare.item_id.in_(item_ids)).delete(synchronize_session=False)
    
    for assignment in payload.assignments:
        user_ids = assignment.user_ids
        if not user_ids:
            continue
        fraction = 1.0 / len(user_ids)
        for uid in user_ids:
            db.add(models.ItemShare(
                item_id=assignment.item_id,
                user_id=uid,
                share_fraction=fraction
            ))
            
    db.commit()
    return {"message": "Bulk assignment successful"}

@router.get("/summary/{receipt_id}")
def get_receipt_summary(receipt_id: int, db: Session = Depends(get_db)):
    return calculate_receipt_totals(receipt_id, db)

@router.post("/assign-user-shares")
def assign_user_shares(payload: schemas.UserShareRequest, db: Session = Depends(get_db)):
    """Called by a guest/host to assign their shares (e.g. Full, /2, /3, /4 or custom) for items."""
    receipt_items = db.query(models.Item).filter(models.Item.receipt_id == payload.receipt_id).all()
    receipt_item_ids = [item.id for item in receipt_items]

    if receipt_item_ids:
        db.query(models.ItemShare).filter(
            models.ItemShare.item_id.in_(receipt_item_ids),
            models.ItemShare.user_id == payload.user_id
        ).delete(synchronize_session=False)

    if payload.shares is not None:
        for share in payload.shares:
            if share.item_id in receipt_item_ids and share.fraction > 0:
                frac = min(max(float(share.fraction), 0.0), 10.0) # clamped
                db.add(models.ItemShare(
                    item_id=share.item_id,
                    user_id=payload.user_id,
                    share_fraction=round(frac, 4)
                ))
        db.commit()
    elif payload.item_ids is not None:
        for item_id in payload.item_ids:
            if item_id in receipt_item_ids:
                db.add(models.ItemShare(
                    item_id=item_id,
                    user_id=payload.user_id,
                    share_fraction=1.0
                ))
        db.commit()

        if receipt_item_ids:
            all_shares = db.query(models.ItemShare).filter(
                models.ItemShare.item_id.in_(receipt_item_ids)
            ).all()
            
            item_user_counts = defaultdict(int)
            for share in all_shares:
                item_user_counts[share.item_id] += 1
                
            for share in all_shares:
                if item_user_counts[share.item_id] > 0:
                    share.share_fraction = 1.0 / item_user_counts[share.item_id]
            
            db.commit()
    
    return {"message": "User shares updated successfully"}