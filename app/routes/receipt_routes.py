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
    return receipt