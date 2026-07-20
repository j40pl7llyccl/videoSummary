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
from faster_whisper import WhisperModel

# Import our storage module
import storage

def clean_temp_dir():
    """Cleans up all files in the temp directory."""
    # We now use the structured storage directories
    for directory in [storage.RAW_DIR, storage.AUDIO_DIR, storage.CLIPS_DIR, storage.DRAFTS_DIR]:
        if directory.exists():
            for item in directory.iterdir():
                if item.is_file():
                    try:
                        item.unlink()
                    except Exception as e:
                        print(f"Could not delete {item}: {e}")

def download_video(url, progress_callback=None):
    """Downloads a video from a URL (YouTube, etc.) using yt-dlp to raw directory."""
    if progress_callback:
        progress_callback("正在分析影片網址...")
    
    outtmpl = str(storage.RAW_DIR / "downloaded_video.%(ext)s")
    
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
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return duration

def extract_audio(video_path, progress_callback=None):
    """Extracts audio from video file to WAV format (16kHz, mono) for Whisper."""
    if progress_callback:
        progress_callback("正在使用 FFmpeg 提取影片音訊...")
    
    video_path = Path(video_path)
    audio_path = storage.AUDIO_DIR / f"{video_path.stem}.wav"
    
    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        str(audio_path)
    ]
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"FFmpeg audio extraction error: {result.stderr}")
        raise Exception("提取音訊時發生 FFmpeg 錯誤。")
        
    if progress_callback:
        progress_callback(f"音訊提取完成: {audio_path.name}")
    return audio_path

def transcribe_audio(audio_path, progress_callback=None):
    """Transcribes audio using faster-whisper and returns segments."""
    if progress_callback:
        progress_callback("正在載入 Whisper 模型進行語音識別 (首次載入需時)...")
    
    model_size = "base"
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as e:
        if progress_callback:
            progress_callback(f"無法以 CPU (int8) 載入: {e}，改用預設 CPU 模式...")
        model = WhisperModel(model_size, device="cpu")

    if progress_callback:
        progress_callback("開始進行語音轉文字識別...")
        
    segments, info = model.transcribe(str(audio_path), beam_size=5)
    
    transcribed_segments = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            transcribed_segments.append({
                'start': round(segment.start, 2),
                'end': round(segment.end, 2),
                'text': text
            })
            if progress_callback:
                progress_callback(f" 識別中: [{segment.start:.1f}s - {segment.end:.1f}s] {text}")
            
    return transcribed_segments

def analyze_transcript_with_ollama(transcripts, model_name="qwen2.5", progress_callback=None):
    """Sends transcripts to Ollama to identify key step timestamps."""
    if not transcripts:
        if progress_callback:
            progress_callback("無語音逐字稿，無法進行 Ollama 語義分析。")
        return []

    if progress_callback:
        progress_callback(f"正在使用 Ollama ({model_name}) 分析逐字稿語義並擷取關鍵步驟...")
    
    transcript_text = ""
    for seg in transcripts:
        transcript_text += f"[{seg['start_time']}s - {seg['end_time']}s]: {seg['text']}\n"
        
    prompt = f"""
你是一位專業的烘焙教學影音編輯。以下是一段麵包製作教學影片的語音識別逐字稿（包含時間戳）：

{transcript_text}

請從逐字稿中分析並辨識出所有關鍵烘焙步驟（例如：揉麵/攪拌/出筋、發酵、整形/滾圓/割紋/裝飾、送入烤箱/烘烤、切片/成品展示等）。
為每個關鍵步驟找出明確的開始時間 (start_time) 與結束時間 (end_time)，單位為秒。

請務必只輸出一個 JSON 陣列（Array），每個元素包含：
- "start_time": 數字 (秒)
- "end_time": 數字 (秒)
- "description": 步驟描述 (繁體中文)

範例格式：
[
  {{"start_time": 12.5, "end_time": 45.2, "description": "揉麵與攪拌麵團"}},
  {{"start_time": 60.0, "end_time": 90.5, "description": "第一次發酵"}}
]

注意：只輸出 JSON 內容本身，絕對不要包含任何額外說明文字或 ```json 的 markdown 標記。
"""
    
    try:
        response = ollama.chat(
            model=model_name,
            messages=[{
                'role': 'user',
                'content': prompt
            }]
        )
        content = response['message']['content']
        clean_content = re.sub(r'^```json\s*|```$', '', content.strip())
        
        match = re.search(r'\[\s*\{.*\}\s*\]', clean_content, re.DOTALL)
        if match:
            clean_content = match.group(0)
            
        results = json.loads(clean_content)
        return results
    except Exception as e:
        if progress_callback:
            progress_callback(f"Ollama 分析失敗: {e}。使用預設時間段分段。")
        return []

def analyze_with_gemini(video_path, api_key, progress_callback=None):
    """Uploads video to Gemini File API and analyzes timestamps (kept for Compatibility)."""
    if not api_key:
        raise ValueError("請提供 Gemini API Key。")
    
    genai.configure(api_key=api_key)
    if progress_callback:
        progress_callback("正在上傳影片至 Gemini API 進行多模態分析 (這可能需要 1-3 分鐘)...")
    
    video_file = genai.upload_file(path=str(video_path))
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
    try:
        genai.delete_file(video_file.name)
    except Exception as e:
        print(f"無法刪除雲端暫存檔: {e}")
        
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        clean_text = re.sub(r'^```json\s*|```$', '', response.text.strip())
        return json.loads(clean_text)

def analyze_with_ollama(video_path, model_name="qwen2.5", progress_callback=None):
    """Refactored Mode B: Whisper STT + Ollama NLP workflow with SQLite storage integration."""
    video_duration = get_video_duration(video_path)
    
    # Save/Retrieve from DB
    video_id = storage.add_video(video_path, duration=video_duration, status="processing")
    
    # Step 1: Extract Audio
    audio_path = extract_audio(video_path, progress_callback)
    
    # Step 2: Transcribe using Whisper
    segments = transcribe_audio(audio_path, progress_callback)
    
    # Save transcripts to DB
    storage_segments = [{'start': s['start'], 'end': s['end'], 'text': s['text']} for s in segments]
    storage.add_transcript_segments(video_id, storage_segments)
    
    # Step 3: Run Ollama on Transcripts
    db_transcripts = storage.get_transcripts(video_id)
    timestamps = analyze_transcript_with_ollama(db_transcripts, model_name, progress_callback)
    
    if not timestamps:
        if progress_callback:
            progress_callback("Ollama 未成功回傳識別步驟，將自動分段...")
        timestamps = [
            {"start_time": 0, "end_time": min(10, video_duration), "description": "影片開頭"},
            {"start_time": round(video_duration/2 - 5, 1), "end_time": min(round(video_duration/2 + 5, 1), video_duration), "description": "關鍵教學中段"},
            {"start_time": max(0, round(video_duration - 10, 1)), "end_time": round(video_duration, 1), "description": "成品與結論展示"}
        ]
        
    # Save clips metadata to DB
    storage.add_clips(video_id, timestamps)
    storage.update_video_status(video_id, "completed", duration=video_duration)
    
    return timestamps

def cut_and_merge_video(video_path, timestamps, progress_callback=None):
    """Cuts clips using fast FFmpeg copy mode and merges them."""
    if progress_callback:
        progress_callback("開始進行 FFmpeg 快速粗剪段落...")
        
    clip_files = []
    
    # Cut segments using fast stream copy (-c copy)
    for i, ts in enumerate(timestamps):
        start = ts['start_time']
        end = ts['end_time']
        desc = ts['description']
        duration = end - start
        
        if duration <= 0:
            continue
            
        clip_path = storage.CLIPS_DIR / f"clip_{i:03d}.mp4"
        if progress_callback:
            progress_callback(f" 正在高速粗剪第 {i+1} 段：{desc} ({start}s - {end}s)")
            
        # Use stream copy for maximum speed
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-to', str(end),
            '-i', str(video_path),
            '-c', 'copy',
            str(clip_path)
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            # Fallback to transcoding if copy fails (e.g. keyframe issue)
            cmd_transcode = [
                'ffmpeg', '-y',
                '-ss', str(start),
                '-to', str(end),
                '-i', str(video_path),
                '-vf', 'scale=1280:720,fps=30',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac',
                str(clip_path)
            ]
            subprocess.run(cmd_transcode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
        clip_files.append(clip_path)
        
    if not clip_files:
        raise Exception("未生成任何有效剪輯片段。")
        
    # Write concat text file
    concat_file_path = storage.CLIPS_DIR / "concat_list.txt"
    with open(concat_file_path, "w", encoding="utf-8") as f:
        for clip in clip_files:
            escaped_path = str(clip.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
            
    output_path = storage.STORAGE_DIR / "condensed_bread_guide.mp4"
    
    if progress_callback:
        progress_callback("正在合併所有粗剪片段，產出最終影片...")
        
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
        raise Exception("合併剪輯片段時發生 FFmpeg 錯誤。")
        
    if progress_callback:
        progress_callback(f"成功產出精簡版影片！路徑：{output_path}")
        
    return output_path
