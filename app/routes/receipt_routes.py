from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services.gemini_service import parse_receipt_with_gemini

router = APIRouter(prefix="/receipts", tags=["Receipts"])

@router.post("/scan", response_model=schemas.ReceiptResponse)
async def scan_and_save_receipt(
    uploader_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        image_bytes = await file.read()
        parsed_data = parse_receipt_with_gemini(image_bytes, mime_type=file.content_type or "image/jpeg")

        # Create Receipt DB Record
        db_receipt = models.Receipt(
            uploader_id=uploader_id,
            store_name=parsed_data.get("store_name") or "Unknown Store",
            total_amount=float(parsed_data.get("total_amount") or 0.0)
        )
        db.add(db_receipt)
        db.commit()
        db.refresh(db_receipt)

        # Save Items
        for item in parsed_data.get("items", []):
            if isinstance(item, dict) and item.get("item_name"):
                db_item = models.Item(
                    receipt_id=db_receipt.id,
                    item_name=str(item.get("item_name", "Item")),
                    price=float(item.get("price") or 0.0)
                )
                db.add(db_item)
        
        db.commit()
        db.refresh(db_receipt)
        return db_receipt
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{receipt_id}", response_model=schemas.ReceiptResponse)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    uploader = db.query(models.User).filter(models.User.id == receipt.uploader_id).first()
    return schemas.ReceiptResponse(
        id=receipt.id,
        store_name=receipt.store_name,
        total_amount=float(receipt.total_amount),
        uploader_id=receipt.uploader_id,
        uploader_name=uploader.name if uploader else "Unknown",
        uploader_upi_id=uploader.upi_id if uploader else None,
        items=[schemas.ItemResponse.model_validate(item) for item in receipt.items]
    )

@router.get("/history/user/{user_id}", response_model=list[schemas.ReceiptHistoryItem])
def get_user_receipt_history(user_id: int, db: Session = Depends(get_db)):
    """Retrieve all receipts that the user uploaded or joined as a participant."""
    # Find all receipt IDs the user participated in via ItemShare
    participated_receipt_ids = (
        db.query(models.Item.receipt_id)
        .join(models.ItemShare, models.ItemShare.item_id == models.Item.id)
        .filter(models.ItemShare.user_id == user_id)
        .distinct()
        .all()
    )
    part_ids = [r[0] for r in participated_receipt_ids]

    # Query receipts where user is uploader OR participant
    receipts = (
        db.query(models.Receipt)
        .filter(
            (models.Receipt.uploader_id == user_id) | (models.Receipt.id.in_(part_ids))
        )
        .order_by(models.Receipt.id.desc())
        .all()
    )

    history = []
    for r in receipts:
        uploader = db.query(models.User).filter(models.User.id == r.uploader_id).first()
        uploader_name = uploader.name if uploader else "Unknown"
        is_uploader = (r.uploader_id == user_id)

        # Calculate this user's personal share cost
        my_shares = (
            db.query(models.ItemShare, models.Item)
            .join(models.Item, models.ItemShare.item_id == models.Item.id)
            .filter(models.Item.receipt_id == r.id, models.ItemShare.user_id == user_id)
            .all()
        )
        my_cost = sum(float(item.price) * float(share.share_fraction) for share, item in my_shares)

        created_str = r.created_at.strftime("%b %d, %Y - %I:%M %p") if r.created_at else "Recent"

        history.append(schemas.ReceiptHistoryItem(
            id=r.id,
            store_name=r.store_name or "Store Receipt",
            total_amount=float(r.total_amount),
            created_at=created_str,
            is_uploader=is_uploader,
            uploader_name=uploader_name,
            my_share_cost=round(my_cost, 2),
            items_count=len(r.items)
        ))

    return history