import os
import re
import json
import time
import shutil
import subprocess
import cv2
import base64
from pathlib import Path
import google.generativeai as genai
import yt_dlp
import ollama

# Create temporary directories if they don't exist
TEMP_DIR = Path("C:/Users/j40pl/.gemini/antigravity-ide/scratch/bread_video_generator/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def clean_temp_dir():
    """Cleans up all files in the temp directory."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

def download_video(url, progress_callback=None):
    """Downloads a video from a URL (YouTube, etc.) using yt-dlp."""
    if progress_callback:
        progress_callback("正在分析影片網址...")
    
    outtmpl = str(TEMP_DIR / "downloaded_video.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
    if progress_callback:
        progress_callback(f"影片下載完成: {Path(filename).name}")
    return filename

def get_video_duration(video_path):
    """Gets the duration of the video in seconds using OpenCV."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0
    fps = cap.get(fps := cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return duration

def analyze_with_gemini(video_path, api_key, progress_callback=None):
    """Uploads video to Gemini File API and analyzes timestamps."""
    if not api_key:
        raise ValueError("請提供 Gemini API Key。")
    
    genai.configure(api_key=api_key)
    
    if progress_callback:
        progress_callback("正在上傳影片至 Gemini API 進行多模態分析 (這可能需要 1-3 分鐘)...")
    
    # Upload video
    video_file = genai.upload_file(path=str(video_path))
    
    # Wait for processing
    while video_file.state.name == "PROCESSING":
        if progress_callback:
            progress_callback("Gemini 正在後台處理/解碼影片...")
        time.sleep(5)
        video_file = genai.get_file(video_file.name)
        
    if video_file.state.name == "FAILED":
        raise Exception("Gemini 影片處理失敗。")

    if progress_callback:
        progress_callback("影片處理完畢，正由 Gemini 1.5 Flash 辨識步驟時間軸...")
        
    prompt = """
    你是一位專業的烘焙教學影音編輯。請仔細分析這段麵包製作影片。
    辨識出所有關鍵烘焙步驟（例如：攪拌/揉麵、第一次發酵、整形、第二次發酵、割紋/裝飾、烘烤、出爐/切片）。
    請為每個關鍵步驟找出明確的開始時間 (start_time) 與結束時間 (end_time)，單位為秒。
    
    請務必只輸出一個 JSON 陣列（Array），每個元素包含：
    - "start_time": 數字 (秒)
    - "end_time": 數字 (秒)
    - "description": 步驟描述 (繁體中文)
    
    範例格式：
    [
      {"start_time": 12, "end_time": 45, "description": "攪拌麵團與揉麵"},
      {"start_time": 60, "end_time": 90, "description": "第一次發酵"}
    ]
    
    注意：只輸出 JSON 內容本身，絕對不要包含任何額外說明文字或 ```json 的 markdown 標記。
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={"response_mime_type": "application/json"}
    )
    
    response = model.generate_content([video_file, prompt])
    
    # Clean up file in cloud
    try:
        genai.delete_file(video_file.name)
    except Exception as e:
        print(f"無法刪除雲端暫存檔: {e}")
        
    # Parse result
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        if progress_callback:
            progress_callback("解析 Gemini 回傳的 JSON 失敗，嘗試使用正則表達式清理...")
        clean_text = re.sub(r'^```json\s*|```$', '', response.text.strip())
        return json.loads(clean_text)

def analyze_with_ollama(video_path, model_name="qwen2-vl:2b", progress_callback=None):
    """Mode B: Extracts frames and analyzes sequentially via Ollama local vision model."""
    if progress_callback:
        progress_callback(f"開始本地 SLM 分析模式 ({model_name})。正在抽取影格...")
        
    # Get video properties
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise Exception("無法讀取影片檔案。")
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    # Sample 1 frame every 8 seconds to prevent overwhelming the context window
    sample_interval = 8  # seconds
    frame_step = int(fps * sample_interval)
    
    sampled_frames = []
    current_frame_idx = 0
    
    while current_frame_idx < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        timestamp = current_frame_idx / fps
        # Resize to smaller resolution to fit context faster
        max_size = 480
        h, w = frame.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            
        # Encode to JPEG base64
        _, buffer = cv2.imencode('.jpg', frame)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        sampled_frames.append({
            'timestamp': timestamp,
            'image_b64': img_base64
        })
        current_frame_idx += frame_step
        
    cap.release()
    
    if progress_callback:
        progress_callback(f"已成功抽取 {len(sampled_frames)} 張關鍵影格，開始使用 Ollama 進行逐步辨識...")
        
    key_steps = []
    
    for idx, item in enumerate(sampled_frames):
        ts = item['timestamp']
        if progress_callback:
            progress_callback(f"正在分析 {ts:.1f} 秒處的畫面 ({idx + 1}/{len(sampled_frames)})...")
            
        prompt = f"""
        這是一張麵包製作教學影片在第 {ts:.1f} 秒處的畫面。
        請判斷此畫面是否正在進行以下「關鍵製作步驟」之一：
        - 揉麵/攪拌/出筋
        - 滾圓/發酵 (包含初次發酵、二次發酵)
        - 整形/滾圓/割紋/裝飾
        - 送入烤箱/烘烤中/出爐
        - 切片/展示成品
        
        請用繁體中文回答，只輸出一個 JSON 物件，格式如下：
        {{
          "is_key_step": true 或是 false,
          "step_name": "步驟名稱(例如: 揉麵攪拌)" (若為 false 則為 ""),
          "description": "簡短描述畫面中的動作" (若為 false 則為 "")
        }}
        
        注意：只輸出 JSON，不要有額外贅字或 markdown 格式。
        """
        
        try:
            response = ollama.chat(
                model=model_name,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [base64.b64decode(item['image_b64'])]
                }]
            )
            content = response['message']['content']
            clean_content = re.sub(r'^```json\s*|```$', '', content.strip())
            result = json.loads(clean_content)
            
            if result.get('is_key_step') and result.get('step_name'):
                key_steps.append({
                    'timestamp': ts,
                    'step_name': result['step_name'],
                    'description': result['description']
                })
        except Exception as e:
            # Fallback/skip if frame analysis fails
            print(f"分析 {ts} 秒影格出錯: {e}")
            
    # Process key_steps list and construct segments
    # Group consecutive detections of the same or similar step names
    if not key_steps:
        if progress_callback:
            progress_callback("Ollama 未偵測到任何關鍵步驟，將默認剪輯整段影片的前、中、後段。")
        return [
            {"start_time": 0, "end_time": min(10, duration), "description": "影片開頭"},
            {"start_time": duration/2 - 5, "end_time": min(duration/2 + 5, duration), "description": "影片中段"},
            {"start_time": max(0, duration - 10), "end_time": duration, "description": "成品展示"}
        ]
        
    # Group steps
    segments = []
    current_segment = None
    
    for step in key_steps:
        if current_segment is None:
            current_segment = {
                "step_name": step['step_name'],
                "start_time": max(0, step['timestamp'] - 3), # Buffer of 3s before
                "end_time": min(duration, step['timestamp'] + 5), # Buffer of 5s after
                "description": step['description']
            }
        else:
            # If the step is detected again within 20 seconds, extend the current segment
            if step['timestamp'] - current_segment['end_time'] < 20:
                current_segment['end_time'] = min(duration, step['timestamp'] + 5)
                # update description if more detailed
                if len(step['description']) > len(current_segment['description']):
                    current_segment['description'] = step['description']
            else:
                segments.append(current_segment)
                current_segment = {
                    "step_name": step['step_name'],
                    "start_time": max(0, step['timestamp'] - 3),
                    "end_time": min(duration, step['timestamp'] + 5),
                    "description": step['description']
                }
                
    if current_segment:
        segments.append(current_segment)
        
    # Final cleanup of segments format
    formatted_segments = []
    for s in segments:
        formatted_segments.append({
            "start_time": round(s["start_time"], 1),
            "end_time": round(s["end_time"], 1),
            "description": s["description"]
        })
        
    return formatted_segments

def cut_and_merge_video(video_path, timestamps, progress_callback=None):
    """Cuts clips based on timestamps and merges them using FFmpeg."""
    if progress_callback:
        progress_callback("開始進行 FFmpeg 剪輯與轉碼作業...")
        
    clips_dir = TEMP_DIR / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    
    clip_files = []
    
    # Trim and normalize each segment
    for i, ts in enumerate(timestamps):
        start = ts['start_time']
        end = ts['end_time']
        desc = ts['description']
        duration = end - start
        
        if duration <= 0:
            continue
            
        clip_path = clips_dir / f"clip_{i:03d}.mp4"
        if progress_callback:
            progress_callback(f"正在剪輯第 {i+1} 段：{desc} ({start}s - {end}s)")
            
        # Re-encode to ensure matching format, resolution (e.g. scale to 1280x720), frame rate, and audio codec
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-to', str(end),
            '-i', str(video_path),
            '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-ar', '44100',
            '-ac', '2',
            str(clip_path)
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"FFmpeg trim error details: {result.stderr}")
            raise Exception(f"剪輯段落 {desc} 時發生 FFmpeg 錯誤。")
            
        clip_files.append(clip_path)
        
    if not clip_files:
        raise Exception("未生成任何有效剪輯片段。")
        
    # Write concat text file
    concat_file_path = TEMP_DIR / "concat_list.txt"
    with open(concat_file_path, "w", encoding="utf-8") as f:
        for clip in clip_files:
            # Escape single quotes in filenames for FFmpeg
            escaped_path = str(clip.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
            
    output_path = Path("C:/Users/j40pl/.gemini/antigravity-ide/scratch/bread_video_generator/condensed_bread_guide.mp4")
    
    if progress_callback:
        progress_callback("正在合併所有剪輯片段，產出最終影片...")
        
    # Concatenate clips
    merge_cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_file_path),
        '-c', 'copy',
        str(output_path)
    ]
    
    result = subprocess.run(merge_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"FFmpeg concat error details: {result.stderr}")
        raise Exception("合併剪輯片段時發生 FFmpeg 錯誤。")
        
    if progress_callback:
        progress_callback(f"成功產出精簡版影片！路徑：{output_path}")
        
    return output_path
