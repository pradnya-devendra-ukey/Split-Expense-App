from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app import models, schemas
from app.services.gemini_service import parse_receipt_with_gemini
from app.services.split_service import get_currency_symbol, generate_join_code

router = APIRouter(prefix="/receipts", tags=["Receipts"])

def get_receipt_payers_list(receipt: models.Receipt, db: Session):
    db_payers = (
        db.query(models.ReceiptPayer, models.User)
        .join(models.User, models.ReceiptPayer.user_id == models.User.id)
        .filter(models.ReceiptPayer.receipt_id == receipt.id)
        .all()
    )
    if db_payers:
        return [
            schemas.ReceiptPayerEntry(
                user_id=u.id,
                user_name=u.name,
                upi_id=u.upi_id,
                amount_paid=float(rp.amount_paid)
            )
            for rp, u in db_payers
        ]
    if receipt.uploader_id:
        uploader = db.query(models.User).filter(models.User.id == receipt.uploader_id).first()
        if uploader:
            return [
                schemas.ReceiptPayerEntry(
                    user_id=uploader.id,
                    user_name=uploader.name,
                    upi_id=uploader.upi_id,
                    amount_paid=float(receipt.total_amount)
                )
            ]
    return []

def format_receipt_response(receipt: models.Receipt, db: Session) -> schemas.ReceiptResponse:
    if not receipt.join_code:
        receipt.join_code = generate_join_code(db)
        db.commit()

    uploader = db.query(models.User).filter(models.User.id == receipt.uploader_id).first() if receipt.uploader_id else None
    payers = get_receipt_payers_list(receipt, db)
    currency_code = (receipt.currency or "INR").upper()
    currency_sym = receipt.currency_symbol or get_currency_symbol(currency_code)

    return schemas.ReceiptResponse(
        id=receipt.id,
        join_code=receipt.join_code,
        store_name=receipt.store_name,
        total_amount=float(receipt.total_amount),
        tax_amount=float(receipt.tax_amount or 0.0),
        tip_amount=float(receipt.tip_amount or 0.0),
        tax_split_method=receipt.tax_split_method or "proportional",
        currency=currency_code,
        currency_symbol=currency_sym,
        uploader_id=receipt.uploader_id,
        uploader_name=uploader.name if uploader else "Unknown",
        uploader_upi_id=uploader.upi_id if uploader else None,
        group_id=receipt.group_id,
        items=[schemas.ItemResponse.model_validate(item) for item in receipt.items],
        payers=payers
    )

@router.post("/scan", response_model=schemas.ReceiptResponse)
async def scan_and_save_receipt(
    uploader_id: int,
    currency: Optional[str] = "INR",
    group_id: Optional[int] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        image_bytes = await file.read()
        parsed_data = parse_receipt_with_gemini(image_bytes, mime_type=file.content_type or "image/jpeg")

        uploader = db.query(models.User).filter(models.User.id == uploader_id).first()
        if not uploader:
            raise HTTPException(
                status_code=400,
                detail="User session expired or user does not exist. Please sign in or create an account."
            )

        cur_code = (currency or uploader.default_currency or "INR").upper()
        cur_sym = get_currency_symbol(cur_code)
        join_code = generate_join_code(db)

        # Create Receipt DB Record
        db_receipt = models.Receipt(
            join_code=join_code,
            uploader_id=uploader_id,
            group_id=group_id,
            store_name=parsed_data.get("store_name") or "Store Receipt",
            total_amount=float(parsed_data.get("total_amount") or 0.0),
            currency=cur_code,
            currency_symbol=cur_sym
        )
        db.add(db_receipt)
        db.commit()
        db.refresh(db_receipt)

        # Add initial default payer (the uploader)
        db.add(models.ReceiptPayer(
            receipt_id=db_receipt.id,
            user_id=uploader_id,
            amount_paid=float(db_receipt.total_amount)
        ))

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

        return format_receipt_response(db_receipt, db)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/manual", response_model=schemas.ReceiptResponse)
def create_manual_receipt(payload: schemas.ManualReceiptCreate, db: Session = Depends(get_db)):
    """Create a new receipt manually without scanning an image."""
    uploader = db.query(models.User).filter(models.User.id == payload.uploader_id).first()
    if not uploader:
        raise HTTPException(status_code=400, detail="Uploader user does not exist.")

    cur_code = (payload.currency or uploader.default_currency or "INR").upper()
    cur_sym = get_currency_symbol(cur_code)
    join_code = generate_join_code(db)

    # Calculate item sum
    items_sum = sum(item.price for item in payload.items)
    tax = float(payload.tax_amount or 0.0)
    tip = float(payload.tip_amount or 0.0)
    total = round(items_sum + tax + tip, 2)

    db_receipt = models.Receipt(
        join_code=join_code,
        uploader_id=payload.uploader_id,
        group_id=payload.group_id,
        store_name=payload.store_name.strip() or "Custom Bill",
        total_amount=total,
        tax_amount=tax,
        tip_amount=tip,
        tax_split_method=payload.tax_split_method or "proportional",
        currency=cur_code,
        currency_symbol=cur_sym
    )
    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)

    # Initial payer is uploader
    db.add(models.ReceiptPayer(
        receipt_id=db_receipt.id,
        user_id=payload.uploader_id,
        amount_paid=total
    ))

    # Add items
    for itm in payload.items:
        db.add(models.Item(
            receipt_id=db_receipt.id,
            item_name=itm.item_name.strip() or "Item",
            price=round(float(itm.price), 2)
        ))

    db.commit()
    db.refresh(db_receipt)

    return format_receipt_response(db_receipt, db)

@router.get("/code/{join_code}", response_model=schemas.ReceiptResponse)
def get_receipt_by_code(join_code: str, db: Session = Depends(get_db)):
    """Retrieve receipt details by 6-character private alphanumeric code."""
    clean_code = join_code.strip().upper()
    receipt = db.query(models.Receipt).filter(models.Receipt.join_code == clean_code).first()
    if not receipt:
        raise HTTPException(status_code=404, detail=f"No receipt found with code '{clean_code}'")
    return format_receipt_response(receipt, db)

@router.get("/{receipt_id}", response_model=schemas.ReceiptResponse)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return format_receipt_response(receipt, db)

@router.post("/{receipt_id}/items", response_model=schemas.ReceiptResponse)
def add_receipt_item(receipt_id: int, payload: schemas.ItemCreate, db: Session = Depends(get_db)):
    """Add a new item to an existing receipt."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    new_item = models.Item(
        receipt_id=receipt.id,
        item_name=payload.item_name.strip() or "New Item",
        price=round(float(payload.price), 2)
    )
    db.add(new_item)
    db.commit()

    # Recalculate receipt total
    all_items = db.query(models.Item).filter(models.Item.receipt_id == receipt.id).all()
    items_sum = sum(float(i.price) for i in all_items)
    receipt.total_amount = round(items_sum + float(receipt.tax_amount or 0.0) + float(receipt.tip_amount or 0.0), 2)
    db.commit()
    db.refresh(receipt)

    return format_receipt_response(receipt, db)

@router.put("/{receipt_id}/items/{item_id}", response_model=schemas.ReceiptResponse)
def edit_receipt_item(receipt_id: int, item_id: int, payload: schemas.ItemUpdate, db: Session = Depends(get_db)):
    """Update name and/or price of an existing receipt item."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    item = db.query(models.Item).filter(models.Item.id == item_id, models.Item.receipt_id == receipt_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found on this receipt")

    if payload.item_name is not None:
        item.item_name = payload.item_name.strip() or item.item_name
    if payload.price is not None:
        item.price = round(float(payload.price), 2)
    db.commit()

    # Recalculate receipt total
    all_items = db.query(models.Item).filter(models.Item.receipt_id == receipt.id).all()
    items_sum = sum(float(i.price) for i in all_items)
    receipt.total_amount = round(items_sum + float(receipt.tax_amount or 0.0) + float(receipt.tip_amount or 0.0), 2)
    db.commit()
    db.refresh(receipt)

    return format_receipt_response(receipt, db)

@router.delete("/{receipt_id}/items/{item_id}", response_model=schemas.ReceiptResponse)
def delete_receipt_item(receipt_id: int, item_id: int, db: Session = Depends(get_db)):
    """Delete an item from a receipt and its associated shares."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    item = db.query(models.Item).filter(models.Item.id == item_id, models.Item.receipt_id == receipt_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found on this receipt")

    db.delete(item)
    db.commit()

    # Recalculate receipt total
    all_items = db.query(models.Item).filter(models.Item.receipt_id == receipt.id).all()
    items_sum = sum(float(i.price) for i in all_items)
    receipt.total_amount = round(items_sum + float(receipt.tax_amount or 0.0) + float(receipt.tip_amount or 0.0), 2)
    db.commit()
    db.refresh(receipt)

    return format_receipt_response(receipt, db)

@router.put("/{receipt_id}/tax-tip", response_model=schemas.ReceiptResponse)
def update_tax_and_tip(receipt_id: int, payload: schemas.TaxTipUpdate, db: Session = Depends(get_db)):
    """Update tax, tip and distribution method (proportional vs equal)."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt.tax_amount = round(float(payload.tax_amount or 0.0), 2)
    receipt.tip_amount = round(float(payload.tip_amount or 0.0), 2)
    receipt.tax_split_method = payload.tax_split_method.lower() if payload.tax_split_method in ["proportional", "equal"] else "proportional"

    all_items = db.query(models.Item).filter(models.Item.receipt_id == receipt.id).all()
    items_sum = sum(float(i.price) for i in all_items)
    receipt.total_amount = round(items_sum + float(receipt.tax_amount) + float(receipt.tip_amount), 2)
    db.commit()
    db.refresh(receipt)

    return format_receipt_response(receipt, db)

@router.put("/{receipt_id}/currency", response_model=schemas.ReceiptResponse)
def update_receipt_currency(receipt_id: int, currency: str = Query(..., min_length=2, max_length=10), db: Session = Depends(get_db)):
    """Update the currency code for a receipt."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    cur_code = currency.strip().upper()
    receipt.currency = cur_code
    receipt.currency_symbol = get_currency_symbol(cur_code)
    db.commit()
    db.refresh(receipt)

    return format_receipt_response(receipt, db)

@router.get("/history/user/{user_id}", response_model=list[schemas.ReceiptHistoryItem])
def get_user_receipt_history(user_id: int, db: Session = Depends(get_db)):
    """Retrieve all receipts that the user uploaded, paid for, or joined as a participant."""
    participated_receipt_ids = (
        db.query(models.Item.receipt_id)
        .join(models.ItemShare, models.ItemShare.item_id == models.Item.id)
        .filter(models.ItemShare.user_id == user_id)
        .distinct()
        .all()
    )
    part_ids = [r[0] for r in participated_receipt_ids]
    payer_receipt_ids = [r[0] for r in db.query(models.ReceiptPayer.receipt_id).filter(models.ReceiptPayer.user_id == user_id).distinct().all()]

    all_target_ids = set(part_ids + payer_receipt_ids)

    receipts = (
        db.query(models.Receipt)
        .filter(
            (models.Receipt.uploader_id == user_id) | (models.Receipt.id.in_(all_target_ids))
        )
        .order_by(models.Receipt.id.desc())
        .all()
    )

    history = []
    for r in receipts:
        if not r.join_code:
            r.join_code = generate_join_code(db)
            db.commit()

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
        
        # Add proportional tax/tip if applicable
        all_receipt_items = db.query(models.Item).filter(models.Item.receipt_id == r.id).all()
        subtotal = sum(float(it.price) for it in all_receipt_items)
        extra = float(r.tax_amount or 0.0) + float(r.tip_amount or 0.0)
        if subtotal > 0 and extra > 0:
            my_cost += (my_cost / subtotal) * extra

        created_str = r.created_at.strftime("%b %d, %Y - %I:%M %p") if r.created_at else "Recent"
        cur_code = r.currency or "INR"
        cur_sym = r.currency_symbol or get_currency_symbol(cur_code)

        history.append(schemas.ReceiptHistoryItem(
            id=r.id,
            join_code=r.join_code,
            store_name=r.store_name or "Store Receipt",
            total_amount=float(r.total_amount),
            currency=cur_code,
            currency_symbol=cur_sym,
            created_at=created_str,
            is_uploader=is_uploader,
            uploader_name=uploader_name,
            my_share_cost=round(my_cost, 2),
            items_count=len(r.items)
        ))

    return history