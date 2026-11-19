from app.core import storage
from app.models import Clip
from app.schemas import ClipOut


def clip_out(c: Clip, cls=ClipOut, **extra):
    data = cls.model_validate(c, from_attributes=True).model_dump()
    data["status"] = c.status.value
    data["video_url"] = storage.presigned_get(c.render_key) if c.render_key else None
    data["thumbnail_url"] = storage.presigned_get(c.thumbnail_key) if c.thumbnail_key else None
    return cls(**{**data, **extra})
