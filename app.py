import streamlit as st
import os
import time
from pathlib import Path
import condenser
import storage
import capcut_generator

# Configure Streamlit page
st.set_page_config(
    page_title="麵包教學自動化「精學短片」生成系統",
    page_icon="🍞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
st.markdown("""
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght=300;400;600;700&family=Noto+Sans+TC:wght=300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Noto Sans TC', sans-serif;
    }
    
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #120e0a 0%, #1e150d 100%);
        color: #f7ede2;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: rgba(26, 18, 11, 0.9) !important;
        border-right: 1px solid rgba(224, 130, 68, 0.2);
    }
    
    /* Title and headers */
    h1 {
        font-weight: 700;
        background: linear-gradient(90deg, #ffb366, #ff7733);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    
    h2, h3 {
        color: #ffcc99 !important;
    }
    
    /* Custom button styling */
    .stButton>button {
        background: linear-gradient(90deg, #e67300, #ff8c1a) !important;
        color: white !important;
        border: none !important;
        padding: 12px 28px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 15px rgba(230, 115, 0, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(230, 115, 0, 0.6) !important;
    }
    
    /* Glassmorphism containers */
    .glass-card {
        background: rgba(45, 33, 22, 0.6);
        border-radius: 12px;
        padding: 24px;
        border: 1px solid rgba(255, 179, 102, 0.15);
        backdrop-filter: blur(10px);
        margin-bottom: 20px;
    }
    
    /* Success status cards */
    .success-card {
        background: rgba(40, 167, 69, 0.15);
        border: 1px solid rgba(40, 167, 69, 0.3);
        border-radius: 8px;
        padding: 16px;
        color: #d4edda;
    }
</style>
""", unsafe_allow_html=True)

# Main UI Grid
st.markdown("<h1>🍞 麵包教學影片「精學短片」自動生成系統</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #d4a373; font-size: 16px;'>運用 AI (Whisper + Ollama) 與 FFmpeg 技術，一鍵提煉精華並生成 CapCut 剪輯草稿！</p>", unsafe_allow_html=True)
st.write("---")

# Sidebar Configuration
st.sidebar.markdown("<h2 style='text-align: center; margin-bottom: 20px;'>⚙️ 系統參數設定</h2>", unsafe_allow_html=True)

# 1. Input configuration
st.sidebar.subheader("1. 影片輸入來源")
input_type = st.sidebar.radio("選擇輸入方式", ["影片網址 (YouTube 等)", "本地影片路徑"], index=0)

video_url = ""
local_path = ""
if input_type == "影片網址 (YouTube 等)":
    video_url = st.sidebar.text_input("輸入影片網址", placeholder="https://www.youtube.com/watch?v=...")
else:
    local_path = st.sidebar.text_input("輸入本地影片檔案路徑 (MP4/MOV/MKV/AVI)", placeholder="C:/videos/bread_tutorial.mp4")

# 2. AI Mode configuration
st.sidebar.subheader("2. AI 分析模式")
ai_mode = st.sidebar.selectbox("選擇分析模型", ["模式 A：本地 Whisper + Ollama 工作流 (推薦)", "模式 B：Gemini 1.5 Flash (雲端)"], index=0)

gemini_key = ""
ollama_model = "qwen2.5"

if "Gemini" in ai_mode:
    default_key = os.environ.get("GEMINI_API_KEY", "")
    gemini_key = st.sidebar.text_input("Gemini API Key", value=default_key, type="password")
else:
    ollama_model = st.sidebar.selectbox("選擇 Ollama 模型", ["qwen2.5", "llama3.2", "gemma2"], index=0)
    st.sidebar.info("💡 請確保 Ollama 服務已在 Windows 背景運行，且已下載該模型。")

# Run Button
st.sidebar.markdown("<br>", unsafe_allow_html=True)
run_btn = st.sidebar.button("🚀 開始生成精華與草稿", use_container_width=True)

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("<div class='glass-card'><h3>📝 系統重構版運作說明</h3>"
                "1. <strong>提取音軌：</strong>FFmpeg 自動將影片音軌分離為 16kHz WAV 檔案。<br>"
                "2. <strong>語音轉文字 (STT)：</strong>本地 Whisper 模型分析口述逐字稿與精確時間戳。<br>"
                "3. <strong>語義分析 (LLM)：</strong>Ollama 分析逐字稿，自動提取與教學步驟相關的精華片段。<br>"
                "4. <strong>自動粗剪與導出：</strong>FFmpeg 進行快速無損剪輯，並<strong>自動生成 CapCut 剪映草稿項目</strong>，您可以直接在剪映中進行二次創作與加特效！"
                "</div>", unsafe_allow_html=True)
    
    st.markdown("### 📊 執行進度與日誌")
    log_area = st.empty()
    log_area.code("等待開始工作...")

with col2:
    st.markdown("### 🎬 處理狀態與輸出預覽")
    preview_area = st.empty()
    preview_area.info("完成剪輯與草稿生成後，結果將會在此處顯示。")

# Process execution
if run_btn:
    condenser.clean_temp_dir()
    
    logs = []
    def log_callback(message):
        logs.append(message)
        log_area.code("\n".join(logs))
        
    try:
        # Step 1: Resolve Video
        video_to_process = ""
        if input_type == "影片網址 (YouTube 等)":
            if not video_url.strip():
                st.error("請輸入有效的影片網址。")
                st.stop()
            video_to_process = condenser.download_video(video_url, log_callback)
        else:
            if not local_path.strip() or not os.path.exists(local_path):
                st.error("請輸入正確且存在的本地影片路徑。")
                st.stop()
            video_to_process = Path(local_path)
            log_callback(f"載入本地影片: {video_to_process.name}")
            
        # Step 2: AI Timestamp Extraction
        timestamps = []
        if "Gemini" in ai_mode:
            if not gemini_key.strip():
                st.error("請提供 Gemini API Key。")
                st.stop()
            timestamps = condenser.analyze_with_gemini(video_to_process, gemini_key, log_callback)
        else:
            # Run Whisper + Ollama pipeline
            timestamps = condenser.analyze_with_ollama(video_to_process, ollama_model, log_callback)
            
        log_callback(f"AI 識別出 {len(timestamps)} 個主要步驟：")
        for ts in timestamps:
            log_callback(f" - [{ts['start_time']}s - {ts['end_time']}s] {ts['description']}")
            
        # Step 3: FFmpeg Cut and Stitch
        output_file = condenser.cut_and_merge_video(video_to_process, timestamps, log_callback)
        
        # Step 4: Generate CapCut Draft
        log_callback("正在為您生成 CapCut 剪映草稿專案...")
        
        # Collect generated clips paths
        clip_paths = list(storage.CLIPS_DIR.glob("clip_*.mp4"))
        clip_paths.sort()
        
        # Detect CapCut local path on Windows
        user_profile = os.environ.get("USERPROFILE", "")
        capcut_drafts_root = Path(user_profile) / "AppData/Local/CapCut/User Data/Projects/com.lved.capcut"
        
        if capcut_drafts_root.exists():
            draft_folder = capcut_generator.create_capcut_draft(
                project_name=f"麵包自動剪輯_{Path(video_to_process).stem}",
                clip_paths=clip_paths,
                output_dir=capcut_drafts_root
            )
            log_callback(f"🎉 CapCut 草稿已直接寫入剪映草稿夾：{draft_folder.name}")
            st.sidebar.success(f"✨ 已自動導入剪映！請直接開啟剪映 PC 版檢視專案。")
        else:
            draft_folder = capcut_generator.create_capcut_draft(
                project_name=f"麵包自動剪輯_{Path(video_to_process).stem}",
                clip_paths=clip_paths,
                output_dir=storage.DRAFTS_DIR
            )
            log_callback(f"🎉 已將 CapCut 草稿保存在專案目錄：{draft_folder}")
            st.sidebar.warning("💡 未偵測到本地剪映預設路徑。請手動將 drafts 目錄下的 Draft 檔案夾複製到剪映的 Projects 資料夾下。")
            
        log_callback("🎉 所有步驟處理完畢！")
        
        with col2:
            preview_area.empty()
            st.success("✨ 精粗剪短片與剪映草稿生成成功！")
            st.video(str(output_file))
            st.info(f"粗剪合併影片儲存於: {output_file}")
            
            # Show summary table
            st.markdown("#### 📋 精簡影片包含步驟")
            st.table(timestamps)
            
            # Show whisper transcripts
            try:
                video_id = storage.add_video(video_to_process)
                transcripts = storage.get_transcripts(video_id)
                if transcripts:
                    with st.expander("📝 檢視本地 Whisper 語音識別全文逐字稿"):
                        for t in transcripts:
                            st.write(f"[{t['start_time']}s - {t['end_time']}s]: {t['text']}")
            except Exception as ex:
                pass
            
    except Exception as e:
        log_callback(f"❌ 錯誤: {str(e)}")
        st.error(f"執行過程中發生錯誤: {e}")
