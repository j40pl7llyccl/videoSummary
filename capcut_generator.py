import os
import json
import uuid
import time
from pathlib import Path

def generate_uuid():
    """Generates a UUID in uppercase as used by CapCut."""
    return str(uuid.uuid4()).upper()

def create_capcut_draft(project_name, clip_paths, output_dir):
    """
    Generates a CapCut draft directory (draft_content.json and draft_meta.json)
    containing the specified clips arranged sequentially on the timeline.
    """
    output_dir = Path(output_dir)
    draft_folder = output_dir / f"Draft_{int(time.time())}"
    draft_folder.mkdir(parents=True, exist_ok=True)
    
    draft_id = generate_uuid()
    created_time = int(time.time() * 1000000) # microseconds
    
    # 1. Prepare materials list & timeline tracks
    videos_materials = []
    track_segments = []
    
    timeline_cursor = 0 # tracks position on the timeline in microseconds
    
    for idx, path in enumerate(clip_paths):
        path = Path(path)
        if not path.exists():
            continue
            
        # Get duration using cv2 if possible, otherwise assume 5 seconds as fallback
        import cv2
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration_sec = frame_count / fps if fps > 0 else 5.0
        cap.release()
        
        duration_us = int(duration_sec * 1000000) # CapCut uses microseconds
        
        mat_id = generate_uuid()
        seg_id = generate_uuid()
        
        # Define video material
        videos_materials.append({
            "audio_fade": None,
            "cartoon_path": "",
            "category_id": "",
            "category_name": "",
            "duration": duration_us,
            "extra_info": "",
            "file_豪華_info": "",
            "file_name": path.name,
            "file_path": str(path.resolve()),
            "height": 720,
            "id": mat_id,
            "material_name": path.stem,
            "material_status": 0,
            "md5": "",
            "type": "video",
            "width": 1280
        })
        
        # Define segment in track
        track_segments.append({
            "caption_info": None,
            "clip": {
                "alpha": 1.0,
                "flip": {"horizontal": False, "vertical": False},
                "rotation": 0.0,
                "scale": {"x": 1.0, "y": 1.0},
                "transform": {"x": 0.0, "y": 0.0}
            },
            "common_keyframes": [],
            "enable_audio": True,
            "id": seg_id,
            "intensifies_audio_path": "",
            "is_placeholder": False,
            "keyframe_refs": [],
            "material_id": mat_id,
            "render_index": idx,
            "source_timerange": {"duration": duration_us, "start": 0},
            "speed": 1.0,
            "target_timerange": {"duration": duration_us, "start": timeline_cursor},
            "track_attribute": 0,
            "track_render_index": 0,
            "visible": True,
            "volume": 1.0
        })
        
        timeline_cursor += duration_us

    # 2. Build draft_content.json structure
    content = {
        "canvas_config": {"height": 720, "ratio": "original", "width": 1280},
        "color_space": 0,
        "config": {
            "adjust_max_duration_limit": 14400000000,
            "align_free_marker_to_frame": True,
            "align_video_to_audio": False,
            "clip_to_frame": True,
            "original_sound_keep_pitch": True,
            "smart_shot_segment": False
        },
        "duration": timeline_cursor,
        "id": draft_id,
        "keyframe_support_type": 0,
        "materials": {
            "audios": [],
            "beats": [],
            "canvases": [],
            "chromas": [],
            "color_curves": [],
            "drafts": [],
            "effects": [],
            "flowers": [],
            "handwrites": [],
            "headsets": [],
            "images": [],
            "languages": [],
            "materials": [],
            "placeholders": [],
            "reverses": [],
            "sound_channel_mappings": [],
            "speeds": [],
            "stickers": [],
            "tail_leaders": [],
            "texts": [],
            "transitions": [],
            "video_effects": [],
            "videos": videos_materials,
            "vocal_separations": []
        },
        "tracks": [
            {
                "attribute": 0,
                "flag": 0,
                "id": generate_uuid(),
                "segments": track_segments,
                "type": "video"
            }
        ],
        "update_time": created_time,
        "version": 6
    }
    
    # 3. Build draft_meta.json structure
    meta = {
        "draft_id": draft_id,
        "draft_name": project_name,
        "draft_fold_path": str(draft_folder.resolve()),
        "draft_updated_time": int(created_time / 1000000),
        "draft_created_time": int(created_time / 1000000),
        "tm_draft_modified": int(created_time / 1000000),
        "draft_type": "video"
    }
    
    # Write to files
    with open(draft_folder / "draft_content.json", "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
        
    with open(draft_folder / "draft_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        
    return draft_folder
