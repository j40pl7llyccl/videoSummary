# 🍞 麵包教學自動化「精學短片」生成系統

本系統專為 Windows 11 原生環境設計，能將冗長的手工麵包製作影片，自動分析並剪輯拼接為包含關鍵步驟（攪拌、發酵、整形、烘焙等）的精華教學短片 `condensed_bread_guide.mp4`。

## 🛠️ 環境與工具安裝指南

### 1. 安裝系統相依套件 (透過 PowerShell)

請使用管理員權限開啟 Windows 11 PowerShell 執行以下命令安裝 FFmpeg 與 Python 3.11：

```powershell
# 安裝 FFmpeg
winget install Gyan.FFmpeg

# 安裝 Python 3.11
winget install Python.Python.3.11

# (選用) 安裝 Ollama 本地 SLM 引擎
winget install Ollama.Ollama
```
*安裝完成後，建議重新啟動 PowerShell 或終端機以更新環境變數路徑。*

---

### 2. 安裝 Python 套件依賴

在專案目錄下執行以下命令安裝所需的 Python 套件：

```powershell
pip install -r requirements.txt
```

---

### 3. 啟動與使用系統

使用以下命令啟動專案的 Web 介面：

```powershell
streamlit run app.py
```

### 💡 模式說明
- **模式 A (雲端預設 - Gemini 1.5 Flash)**:
  - 填入您的 `GEMINI_API_KEY`（或設定為系統環境變數）。
  - Gemini 會直接閱讀整段影片並進行高精度的多模態步驟切片。
- **模式 B (本地 SLM - Ollama)**:
  - 請先在 PowerShell 中執行 `ollama run qwen2-vl:2b` 或 `ollama run llama3.2-vision` 下載模型。
  - 本系統會將影片抽取影格，並逐步傳遞至 Ollama 本地視覺模型進行理解與時間戳剪輯。
