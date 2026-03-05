"""
Announcement endpoints for the High School Management System API
"""

import logging
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _serialize_announcement(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_announcements(active_only: bool = True) -> List[Dict[str, Any]]:
    """Get announcements, optionally filtered to only active ones."""
    query = {}
    if active_only:
        today = date.today().isoformat()
        query = {
            "expiration_date": {"$gte": today},
            "$or": [
                {"start_date": None},
                {"start_date": {"$lte": today}}
            ]
        }

    results = []
    for doc in announcements_collection.find(query).sort("expiration_date", 1):
        results.append(_serialize_announcement(doc))
    return results


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)) -> List[Dict[str, Any]]:
    """Get all announcements (including expired) for management. Requires authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    results = []
    for doc in announcements_collection.find().sort("expiration_date", -1):
        results.append(_serialize_announcement(doc))
    return results


@router.post("")
@router.post("/")
def create_announcement(
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """Create a new announcement. Requires teacher authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Validate expiration date is today or in the future
    try:
        exp_date = date.fromisoformat(expiration_date)
        if exp_date < date.today():
            raise HTTPException(
                status_code=400, detail="Expiration date must be today or in the future")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid expiration date format. Use YYYY-MM-DD")

    # Validate start date if provided
    if start_date:
        try:
            s_date = date.fromisoformat(start_date)
            if s_date > exp_date:
                raise HTTPException(
                    status_code=400, detail="Start date must be before expiration date")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid start date format. Use YYYY-MM-DD")

    announcement = {
        "message": message.strip(),
        "expiration_date": expiration_date,
        "start_date": start_date,
        "created_by": teacher_username
    }

    try:
        result = announcements_collection.insert_one(announcement)
        announcement["id"] = str(result.inserted_id)
        announcement.pop("_id", None)
        return announcement
    except Exception as e:
        logger.error("Failed to create announcement: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create announcement")


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """Update an existing announcement. Requires teacher authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    # Validate expiration date
    try:
        exp_date = date.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid expiration date format. Use YYYY-MM-DD")

    # Validate start date if provided
    if start_date:
        try:
            s_date = date.fromisoformat(start_date)
            if s_date > exp_date:
                raise HTTPException(
                    status_code=400, detail="Start date must be before expiration date")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid start date format. Use YYYY-MM-DD")

    update_data = {
        "message": message.strip(),
        "expiration_date": expiration_date,
        "start_date": start_date
    }

    try:
        announcements_collection.update_one({"_id": obj_id}, {"$set": update_data})
    except Exception as e:
        logger.error("Failed to update announcement: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update announcement")

    update_data["id"] = announcement_id
    update_data["created_by"] = existing.get("created_by")
    return update_data


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
) -> Dict[str, str]:
    """Delete an announcement. Requires teacher authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
