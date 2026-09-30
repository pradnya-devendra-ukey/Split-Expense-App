from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models, schemas
from app.services.split_service import calculate_group_totals, get_currency_symbol

router = APIRouter(prefix="/groups", tags=["Groups"])

def format_group_response(group: models.Group, db: Session) -> schemas.GroupResponse:
    creator = db.query(models.User).filter(models.User.id == group.created_by).first() if group.created_by else None
    
    # Members
    members_data = []
    for gm in group.members:
        u = gm.user
        if u:
            members_data.append(schemas.GroupMemberResponse(
                user_id=u.id,
                user_name=u.name,
                upi_id=u.upi_id,
                joined_at=gm.joined_at.strftime("%b %d, %Y") if gm.joined_at else None
            ))

    # Receipts
    receipts_data = []
    total_spend = 0.0
    for r in group.receipts:
        uploader = db.query(models.User).filter(models.User.id == r.uploader_id).first()
        r_total = float(r.total_amount)
        total_spend += r_total
        receipts_data.append(schemas.GroupReceiptItem(
            receipt_id=r.id,
            join_code=r.join_code,
            store_name=r.store_name or "Receipt",
            total_amount=r_total,
            currency=r.currency or "INR",
            currency_symbol=r.currency_symbol or get_currency_symbol(r.currency),
            created_at=r.created_at.strftime("%b %d, %Y") if r.created_at else "Recent",
            items_count=len(r.items),
            uploader_name=uploader.name if uploader else "Unknown"
        ))

    cur_code = (group.currency or "INR").upper()
    cur_sym = group.currency_symbol or get_currency_symbol(cur_code)

    return schemas.GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        currency=cur_code,
        currency_symbol=cur_sym,
        created_by=group.created_by,
        creator_name=creator.name if creator else "Unknown",
        created_at=group.created_at.strftime("%b %d, %Y") if group.created_at else "Recent",
        members=members_data,
        receipts=receipts_data,
        total_spend=round(total_spend, 2)
    )

@router.post("", response_model=schemas.GroupResponse)
def create_group(payload: schemas.GroupCreate, creator_id: int, db: Session = Depends(get_db)):
    """Create a new group/trip and add initial members."""
    creator = db.query(models.User).filter(models.User.id == creator_id).first()
    if not creator:
        raise HTTPException(status_code=400, detail="Creator user not found")

    cur_code = (payload.currency or creator.default_currency or "INR").upper()
    cur_sym = get_currency_symbol(cur_code)

    db_group = models.Group(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        currency=cur_code,
        currency_symbol=cur_sym,
        created_by=creator_id
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)

    # Always add creator as member
    member_set = set(payload.member_ids or [])
    member_set.add(creator_id)

    for uid in member_set:
        u = db.query(models.User).filter(models.User.id == uid).first()
        if u:
            db.add(models.GroupMember(group_id=db_group.id, user_id=uid))

    db.commit()
    db.refresh(db_group)

    return format_group_response(db_group, db)

@router.get("/user/{user_id}", response_model=List[schemas.GroupResponse])
def get_user_groups(user_id: int, db: Session = Depends(get_db)):
    """Get all groups/trips the user belongs to or created."""
    member_group_ids = [gm.group_id for gm in db.query(models.GroupMember).filter(models.GroupMember.user_id == user_id).all()]
    groups = (
        db.query(models.Group)
        .filter((models.Group.id.in_(member_group_ids)) | (models.Group.created_by == user_id))
        .order_by(models.Group.id.desc())
        .all()
    )
    return [format_group_response(g, db) for g in groups]

@router.get("/{group_id}", response_model=schemas.GroupResponse)
def get_group_details(group_id: int, db: Session = Depends(get_db)):
    """Get group details with all member list and receipts."""
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return format_group_response(group, db)

@router.post("/{group_id}/members", response_model=schemas.GroupResponse)
def add_group_member(group_id: int, payload: schemas.AddGroupMemberRequest, db: Session = Depends(get_db)):
    """Add a member to the group."""
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == payload.user_id
    ).first()

    if not existing:
        db.add(models.GroupMember(group_id=group_id, user_id=payload.user_id))
        db.commit()
        db.refresh(group)

    return format_group_response(group, db)

@router.post("/{group_id}/receipts/{receipt_id}", response_model=schemas.GroupResponse)
def link_receipt_to_group(group_id: int, receipt_id: int, db: Session = Depends(get_db)):
    """Link an existing receipt to a group/trip."""
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt.group_id = group.id
    db.commit()
    db.refresh(group)

    return format_group_response(group, db)

@router.delete("/{group_id}/receipts/{receipt_id}", response_model=schemas.GroupResponse)
def unlink_receipt_from_group(group_id: int, receipt_id: int, db: Session = Depends(get_db)):
    """Unlink a receipt from a group/trip."""
    receipt = db.query(models.Receipt).filter(models.Receipt.id == receipt_id, models.Receipt.group_id == group_id).first()
    if receipt:
        receipt.group_id = None
        db.commit()

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return format_group_response(group, db)

@router.get("/{group_id}/summary", response_model=schemas.GroupSummaryResponse)
def get_group_consolidated_summary(group_id: int, db: Session = Depends(get_db)):
    """Calculate consolidated multi-receipt smart settlement for a trip."""
    summary = calculate_group_totals(group_id, db)
    if not summary:
        raise HTTPException(status_code=404, detail="Group not found")
    return summary
