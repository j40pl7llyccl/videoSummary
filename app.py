import streamlit as st
import os
import time
from pathlib import Path
import condenser

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
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Noto+Sans+TC:wght@300;400;700&display=swap');
    
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
st.markdown("<p style='color: #d4a373; font-size: 16px;'>運用 AI (Gemini 1.5 或 本地 SLM) 與 FFmpeg 技術，一鍵提煉麵包烘焙的精華步驟！</p>", unsafe_allow_html=True)
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
ai_mode = st.sidebar.selectbox("選擇分析模型", ["模式 A：Gemini 1.5 Flash (雲端預設)", "模式 B：本地開源 SLM (Ollama)"], index=0)

gemini_key = ""
ollama_model = "qwen2-vl:2b"

if "Gemini" in ai_mode:
    # Look for env var default
    default_key = os.environ.get("GEMINI_API_KEY", "")
    gemini_key = st.sidebar.text_input("Gemini API Key", value=default_key, type="password", help="如果已設定環境變數 GEMINI_API_KEY，此處會自動載入")
else:
    ollama_model = st.sidebar.selectbox("選擇 Ollama 視覺模型", ["qwen2-vl:2b", "llama3.2-vision"], index=0)
    st.sidebar.info("💡 請確保 Ollama 服務已在 Windows 背景運行，且已下載該模型。")

# Run Button
st.sidebar.markdown("<br>", unsafe_allow_html=True)
run_btn = st.sidebar.button("🚀 開始生成精華影片", use_container_width=True)

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("<div class='glass-card'><h3>📝 系統運作說明</h3>"
                "此工具會自動解析您的教學影片：<br>"
                "1. <strong>影片下載或讀取：</strong>將網址透過 yt-dlp 轉為本地 mp4。<br>"
                "2. <strong>AI 辨識步驟：</strong>透過大語言模型或本地視覺 SLM 分析關鍵畫面的時間戳。<br>"
                "3. <strong>FFmpeg 自動剪輯：</strong>將多個重要步驟時間段無損或轉碼裁剪，並拼接合併為一個完整短片。<br>"
                "4. <strong>產出結果：</strong>儲存為 <code>condensed_bread_guide.mp4</code> 供隨時學習。<br>"
                "</div>", unsafe_allow_html=True)
    
    st.markdown("### 📊 執行進度與日誌")
    log_area = st.empty()
    log_area.code("等待開始工作...")

with col2:
    st.markdown("### 🎬 精簡版影片預覽")
    preview_area = st.empty()
    preview_area.info("完成剪輯後，影片將會在此處顯示。")

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
            timestamps = condenser.analyze_with_ollama(video_to_process, ollama_model, log_callback)
            
        log_callback(f"AI 識別出 {len(timestamps)} 個主要步驟：")
        for ts in timestamps:
            log_callback(f" - [{ts['start_time']}s - {ts['end_time']}s] {ts['description']}")
            
        # Step 3: FFmpeg Cut and Stitch
        output_file = condenser.cut_and_merge_video(video_to_process, timestamps, log_callback)
        
        # Step 4: Finish & Preview
        log_callback("🎉 所有步驟處理完畢！")
        
        with col2:
            preview_area.empty()
            st.success("✨ 精學短片生成成功！")
            st.video(str(output_file))
            st.info(f"產出檔案儲存於: {output_file}")
            
            # Show summary table
            st.markdown("#### 📋 精簡影片包含步驟")
            st.table(timestamps)
            
    except Exception as e:
        log_callback(f"❌ 錯誤: {str(e)}")
        st.error(f"執行過程中發生錯誤: {e}")
