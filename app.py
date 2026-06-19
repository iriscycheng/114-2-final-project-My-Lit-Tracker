import streamlit as st
import pandas as pd
import time
import sys

# 強制將 Windows 終端機輸出設定為 UTF-8，以支援後端列印 Emoji，避免報錯中斷
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# 匯入我們寫好的後端模組 (第一週完成的專案1.py)
import 專案1 as backend
import re

@st.dialog("📖 深度名詞解析")
def show_term_dialog(term, api_key):
    st.markdown(f"**正在查詢「{term}」的深入解析...**")
    with st.spinner("AI 正在解析中..."):
        explanation = backend.analyze_single_term(term, api_key)
    st.markdown("---")
    st.markdown(explanation)

# ==========================================
# 網頁基本設定
# ==========================================
# 設定網頁標題、圖示與版面寬度 (必須放在所有 st 指令的最前面)
st.set_page_config(page_title="My Lit-Tracker", page_icon="🧬", layout="wide")

st.title("🧬 My Lit-Tracker: 自動化文獻追蹤與語義分群系統")
st.markdown("為生醫實驗室打造的文獻超級助理，結合 PubMed, Semantic Scholar 與 Google Gemini API。")

# ==========================================
# 頂部狀態指示燈 (IP 偵測)
# ==========================================
# 使用 session_state 來快取 IP 偵測結果，避免每次重整網頁都重新檢查
if 'is_ntu' not in st.session_state:
    st.session_state.is_ntu = backend.is_public_ip_ntu_range()

if st.session_state.is_ntu:
    st.success("🟢 **權限狀態**：已連線至台大網路 (140.112.*)，可存取完整學術資源！")
else:
    with st.container():
        # 建立自訂樣式的淡紅色警告方框，並將按鈕包含在內
        st.markdown("""
            <style>
            /* 讓包含警告與偵測按鈕的 columns 容器垂直置中 */
            div[data-testid="stHorizontalBlock"]:has(.vpn-btn-marker) {
                align-items: center !important;
            }
            
            /* 清除警告框的預設邊距 */
            div[data-testid="stHorizontalBlock"]:has(.vpn-btn-marker) div[data-testid="stAlert"] {
                margin: 0 !important;
            }
            
            /* 美化按鈕，使其精緻、符合紅褐色警告色系 */
            div[data-testid="stColumn"]:has(.vpn-btn-marker) button {
                background-color: #FFFFFF !important;
                color: #9B1C1C !important;
                border: 1px solid rgba(255, 75, 75, 0.2) !important;
                font-size: 13px !important;
                padding: 6px 12px !important;
                height: auto !important;
                min-height: unset !important;
                margin: 0 !important;
                border-radius: 4px !important;
                line-height: 1.4 !important;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
                width: 100% !important;
            }
            div[data-testid="stColumn"]:has(.vpn-btn-marker) button:hover {
                background-color: #FFF0F0 !important;
                border-color: rgba(255, 75, 75, 0.5) !important;
                color: #771D1D !important;
            }
            </style>
        """, unsafe_allow_html=True)

        col_err, col_btn = st.columns([5, 1])
        with col_err:
            st.error("🔴 **權限狀態**：目前為外部網路。若遇付費文獻，請先開啟 NTU SSL VPN 以獲取全文。")
        with col_btn:
            st.markdown('<div class="vpn-btn-marker"></div>', unsafe_allow_html=True)
            if st.button("重新偵測連線", key="reconnect_vpn_btn"):
                st.session_state.is_ntu = backend.is_public_ip_ntu_range()
                try:
                    st.rerun()
                except AttributeError:
                    st.experimental_rerun()

# ==========================================
# 彈出式使用說明書 (Dialog)
# ==========================================
@st.dialog("My Lit-Tracker 使用說明書", width="large")
def show_user_manual():
    st.markdown("""
<div style="font-size: 14px; line-height: 1.5;">
<h4 style="margin-bottom: 5px; margin-top: 0; font-size: 16px;">架設初衷</h4>
<p style="margin-top: 0; margin-bottom: 12px;">在浩瀚的學術文獻中，研究人員經常面臨「找不到重點」、「迷失在引用叢林」的困境。架設 <b>My Lit-Tracker</b> 的初衷，是為了打造一個能夠自動串聯、過濾並理解學術脈絡的智慧助理，讓研究人員能夠把寶貴的時間花在「思考」而非「搜尋」上。</p>

<h4 style="margin-bottom: 5px; font-size: 16px;">系統核心功能</h4>
<ul style="margin-top: 0; padding-left: 20px; margin-bottom: 12px;">
<li><b>PubMed 文獻廣泛檢索與 AI 動態分群</b>：不只幫您找到文獻，還能根據您的自訂維度，讓 AI 自動將百篇文獻分類，並提煉實驗重點。</li>
<li><b>跨越版權牆的文獻脈絡追蹤</b>：輸入一篇核心論文，系統將同時調用 Semantic Scholar 與 OpenAlex 雙資料庫，為您溯源它的過去（上游）與未來（下游），並提供可一鍵直達期刊官網的連結。</li>
<li><b>AI 脈絡總結與精準文獻打擊 (Top 10)</b>：當關聯文獻量過大時，只要輸入特定的知識點，AI 就會為您從幾百篇論文中，精準挑出最相關的 Top 10 論文供您閱讀。</li>
</ul>

<h4 style="margin-bottom: 5px; font-size: 16px;">操作指南</h4>
<p style="margin-top: 0; margin-bottom: 4px;"><b>【第一步】完成系統設定（左側欄）</b><br>
請先填寫您的「PubMed 聯絡信箱」與「Gemini API Key」。這是啟用搜尋與 AI 智慧過濾功能的前提。</p>

<p style="margin-top: 6px; margin-bottom: 2px;"><b>【第二步】選擇您的任務</b></p>
<ul style="margin-top: 0; padding-left: 20px; margin-bottom: 0;">
<li><b>探索新領域</b>：切換至「搜尋與分群 (PubMed)」分頁。輸入關鍵字抓取文獻後，可在下方輸入您想分類的維度（如：臨床應用），讓 AI 幫您將清單分門別類。</li>
<li><b>深挖關鍵論文</b>：切換至「脈絡追蹤 (Semantic Scholar)」分頁。輸入目標論文的 DOI 碼。
<ul style="margin-bottom: 0;">
<li>點擊 <b>追蹤全部文獻脈絡</b>：可查看完整的上下游發展清單。</li>
<li>輸入關鍵字並點擊 <b>精準篩選 Top 10</b>：讓 AI 直接幫您把最精華、最符合您需求的那 10 篇關聯論文挖出來！</li>
</ul>
</li>
</ul>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 側邊欄 (Sidebar) - 參數設定區
# ==========================================
with st.sidebar:
    # 注入自訂 CSS 來更改按鈕顏色為 #A6A6D2
    st.markdown("""
        <style>
        [data-testid="stSidebar"] [data-testid="stButton"] button {
            background-color: #A6A6D2 !important;
            border-color: #A6A6D2 !important;
            color: white !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] button:hover {
            background-color: #8a8ab8 !important;
            border-color: #8a8ab8 !important;
            color: white !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if st.button("📖 開啟系統使用說明書", use_container_width=True, type="primary"):
        show_user_manual()
        
    st.markdown('<h3 style="font-size: 20px; margin-top: 15px; margin-bottom: 10px;">⚙️ 系統設定</h3>', unsafe_allow_html=True)
    
    user_email = st.text_input("PubMed 聯絡信箱", placeholder="your.email@example.com")
    with st.expander("填寫說明"):
        st.markdown("● **何時填寫**：在「搜尋與分群」分頁進行檢索時。\n● **為什麼填**：PubMed 規定使用程式抓取文獻必須附上信箱，避免被封鎖。")
    
    # 安全作法：嘗試從 .streamlit/secrets.toml 讀取預設金鑰
    try:
        default_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        default_key = ""
        
    gemini_key_input = st.text_input("Gemini API Key", type="password", value="", placeholder="若已在系統後端設定，可留白")
    gemini_key = gemini_key_input if gemini_key_input else default_key
    with st.expander("填寫說明"):
        st.markdown("● **何時填寫**：欲使用「AI 語義分群」或「精準打擊」時。\n● **為什麼填**：系統需要金鑰才能啟動 Google Gemini 3.1 Pro AI 模型。([點此免費申請](https://aistudio.google.com/app/apikey))")
    
    st.markdown("---")
    st.markdown("### 關於專案")
    st.markdown("本系統採用雙引擎設計：\n1. **PubMed API**: 廣泛檢索\n2. **Semantic Scholar API**: 脈絡追蹤")
    st.markdown("核心 AI 引擎：\n- **Google Gemini 2.5 Flash** (主力)\n- **Google Gemini 2.5 Pro** (備用)")

# ==========================================
# 主畫面 - 分頁設計
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔍 搜尋與分群 (PubMed)", "🌐 脈絡追蹤 (Semantic Scholar)", "🔬 單篇精讀 (Deep Read)"])

# ------------------------------------------
# 分頁一：文獻檢索與 AI 動態分群
# ------------------------------------------
with tab1:
    st.subheader("文獻檢索與 AI 動態分群")
    st.caption("• **操作流程**：① **檢索文獻** ➔ ② **挑選並勾選**感興趣的論文 ➔ ③ 輸入特定的研究視角，讓 **AI 為您動態客製化分群**！")
    
    # 搜尋區塊
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("請輸入檢索關鍵字", placeholder="例如：optogenetics cerebellum")
    with col2:
        max_results = st.number_input("抓取篇數", min_value=1, max_value=50, value=10)
        
    # 偵測關鍵字或篇數變更，變更時清空先前的搜尋結果與綠色提示
    if 'prev_query' in st.session_state and (st.session_state.prev_query != search_query or st.session_state.prev_max != max_results):
        st.session_state.pop('search_results', None)
        st.session_state.pop('search_success_msg', None)
        # 清空舊的核取方塊狀態
        for k in list(st.session_state.keys()):
            if k.startswith("paper_check_") or k == "select_all":
                st.session_state.pop(k, None)
    st.session_state.prev_query = search_query
    st.session_state.prev_max = max_results

    # 注入樣式使搜尋按鈕與提示訊息水平對齊、垂直置中
    st.markdown("""
        <style>
        /* 隱藏 marker 容器避免佔用空間 */
        div.element-container:has(.search-btn-marker) {
            display: none !important;
        }
        /* 讓緊隨其後的 columns 容器垂直置中 */
        div.element-container:has(.search-btn-marker) + div[data-testid="stHorizontalBlock"] {
            align-items: center !important;
        }
        /* 清除提示訊息的邊距 */
        div.element-container:has(.search-btn-marker) + div[data-testid="stHorizontalBlock"] div[data-testid="stAlert"] {
            margin: 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="search-btn-marker"></div>', unsafe_allow_html=True)
    col_search_btn, col_search_msg = st.columns([1.2, 8.8])
    with col_search_btn:
        search_clicked = st.button("開始搜尋", type="primary", key="search_pubmed", use_container_width=True)
        
    if search_clicked:
        if not user_email:
            st.error("⚠️ 請先在左側邊欄填寫聯絡信箱！")
        elif not search_query:
            st.warning("⚠️ 請輸入關鍵字！")
        else:
            with st.spinner("正在呼叫 PubMed API 抓取文獻..."):
                results = backend.search_pubmed_titles_abstracts(search_query, user_email, max_results)
                if results:
                    st.session_state.search_results = results
                    st.session_state.search_success_msg = f"✅ 成功找到 {len(results)} 篇文獻！"
                else:
                    st.session_state.search_success_msg = None
                    st.info("找不到相關文獻，請嘗試其他關鍵字。")
                    
    if 'search_results' in st.session_state and st.session_state.get('search_success_msg'):
        with col_search_msg:
            st.success(st.session_state.search_success_msg)

    # 兩階段載入實作 (如果有搜尋結果的話)
    if 'search_results' in st.session_state:
        st.markdown("### 步驟一：挑選感興趣的文獻")
        st.info("💡 兩階段載入設計：請從以下清單中勾選您認為有價值的文獻，再交給 AI 進行深度分析，以節省運算成本。")
        
        # 關鍵字粗體化函數
        def highlight_keywords(text, query):
            if not text or not query:
                return text
            import re
            words = [re.escape(w) for w in query.split() if w.strip()]
            if not words:
                return text
            words.sort(key=len, reverse=True)
            pattern = re.compile(r'(' + '|'.join(words) + r')', re.IGNORECASE)
            return pattern.sub(r'**\1**', text)

        @st.fragment
        def render_abstract_expander(paper, idx, search_query, gemini_key):
            abstract_text = paper.get('abstract', '無摘要')
            with st.expander("📄 檢視摘要預覽", expanded=False):
                highlighted_abs = highlight_keywords(abstract_text, search_query)
                st.markdown(highlighted_abs)
                
                if abstract_text != '無摘要' and st.button("🌐 翻譯摘要", key=f"trans_{idx}"):
                    if not gemini_key:
                        st.error("⚠️ 請先在側邊欄填寫 Gemini API Key")
                    else:
                        translated_text = backend.translate_abstract_with_tooltips(abstract_text, gemini_key)
                        st.markdown("---")
                        st.markdown("##### 翻譯與解析")
                        st.caption("💡 提示：將滑鼠游標停留在藍色專有名詞上，即可查看解釋。")
                        st.markdown(translated_text, unsafe_allow_html=True)

        # 全選 / 取消全選功能
        if 'select_all' not in st.session_state:
            st.session_state.select_all = False

        def toggle_select_all():
            for idx in range(len(st.session_state.search_results)):
                st.session_state[f"paper_check_{idx}"] = st.session_state.select_all

        st.checkbox(
            "🗂️ **全選 / 取消全選 所有搜尋文獻**",
            key="select_all",
            on_change=toggle_select_all
        )
        st.markdown('<div style="margin-bottom: 10px;"></div>', unsafe_allow_html=True)

        selected_papers = []
        for idx, paper in enumerate(st.session_state.search_results):
            # 建立帶有精緻框線的卡片
            with st.container(border=True):
                # 取得期刊資訊並個別進行關鍵字粗體化，避免 markdown 語法干擾
                journal_info = paper.get('journal', '未知期刊')
                doi_info = paper.get('doi', '')
                
                highlighted_title = highlight_keywords(paper['title'], search_query)
                highlighted_journal = highlight_keywords(journal_info, search_query)
                
                if doi_info:
                    combined_label = f"{highlighted_title} — *{highlighted_journal}* &emsp;&emsp; :gray[(DOI: {doi_info})]"
                else:
                    combined_label = f"{highlighted_title} — *{highlighted_journal}*"
                
                # 核取方塊
                check_key = f"paper_check_{idx}"
                is_selected = st.checkbox(
                    combined_label,
                    key=check_key,
                    help="勾選以加入 AI 分析名單"
                )
                if is_selected:
                    selected_papers.append(paper)
                
                # 摘要摺疊面板，使用 fragment 獨立渲染，避免點擊翻譯時整頁重新讀取
                render_abstract_expander(paper, idx, search_query, gemini_key)
        
        if len(selected_papers) > 0:
            st.markdown(f"**已選取 {len(selected_papers)} 篇文獻。**")
            
            st.markdown("### 步驟二：AI 動態客製化分群")
            st.markdown("💡 **不知道要怎麼分群？試試看這些維度：**  \n"
                       "● 實驗動物模型與技術（例如：老鼠、果蠅、特定細胞株等）  \n"
                       "● 受體與分子機制（例如：NMDA、AMPA 或特定蛋白質途徑等）  \n"
                       "● 臨床應用與藥物開發（例如：具備臨床潛力或探討新藥的文獻）  \n"
                       "● 疾病亞型與症狀（例如：依照疾病的不同病理特徵進行分群）")
            focus_dim = st.text_input(
                "請輸入自訂的分類維度", 
                value="", 
                placeholder="例如：實驗動物模型與技術", 
                help="AI 將會戴上這副『過濾眼鏡』，並嚴格依據您定義的這個主題，對上方您勾選的文獻進行分類與重點摘要。"
            )
            
            if st.button("✨ 執行 AI 語義分群", key="run_clustering"):
                if not gemini_key:
                    st.error("⚠️ 請先在左側邊欄填寫 Gemini API Key！")
                else:
                    with st.spinner("正在呼叫 Gemini API 進行語義分析..."):
                        cluster_result = backend.analyze_papers_clustering(selected_papers, focus_dim, gemini_key)
                        
                        if cluster_result:
                            match = re.search(r"<!-- MODEL:(.*?) -->", cluster_result)
                            used_model = match.group(1) if match else "Gemini API"
                            cluster_result = re.sub(r"<!-- MODEL:(.*?) -->\n", "", cluster_result)
                            
                            st.success(f"✅ AI 分析完成！(由 **{used_model}** 生成)")
                            st.markdown(cluster_result)
                            
                            # CSV 匯出功能
                            st.markdown("### 匯出資料")
                            csv_data = pd.DataFrame(selected_papers).to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label="📥 下載已選取的文獻 (CSV)",
                                data=csv_data,
                                file_name='selected_papers.csv',
                                mime='text/csv',
                            )
                        else:
                            st.error("分析失敗，請檢查 API Key 或重試。")

# ------------------------------------------
# 分頁二：脈絡追蹤與知識圖譜
# ------------------------------------------
with tab2:
    st.subheader("文獻脈絡追蹤與知識圖譜")
    st.markdown("輸入一篇核心論文的 DOI，我們將為您溯源其理論基礎（上游）與未來發展（下游）。")
    st.info("💡 **使用方法選擇**：\n\n"
            "● **方法 A**：取得完整上下游文獻清單自行閱讀。  \n"
            "● **方法 B**：由 AI 依據您的關鍵字直接篩選出最精華的 10 篇文獻（可省去閱讀數百篇文獻的時間）。")
    
    # 注入 CSS 讓 Tab 2 內部的問號圈圈按鈕更加精緻，且讓標題與按鈕垂直置中
    st.markdown("""
        <style>
        /* 標題與問號按鈕整排垂直置中 */
        div[data-testid="stHorizontalBlock"]:has(.method-b-header-marker) {
            align-items: center !important;
        }
        /* 將 popover 包裝器靠右對齊 */
        div[data-testid="stColumn"]:has(.method-b-header-marker) [data-testid="stPopover"] {
            margin-left: auto !important;
            width: fit-content !important;
        }
        /* 讓問號 popover 按鈕變成精緻的圓圈問號 */
        div[data-testid="stColumn"]:has(.method-b-header-marker) button {
            border-radius: 50% !important;
            width: 22px !important;
            height: 22px !important;
            min-height: 22px !important;
            min-width: 22px !important;
            max-height: 22px !important;
            max-width: 22px !important;
            padding: 0 !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 13px !important;
            font-weight: bold !important;
            color: #555 !important;
            border: 1px solid #ccc !important;
            background-color: #f9f9f9 !important;
            margin: 0 !important;
            box-shadow: none !important;
            transition: all 0.2s ease !important;
        }
        div[data-testid="stColumn"]:has(.method-b-header-marker) button:hover {
            border-color: #888 !important;
            background-color: #f0f0f0 !important;
            color: #111 !important;
            transform: scale(1.08);
        }
        /* 隱藏 popover 按鈕右側的下拉小箭頭 (Chevron SVG) */
        div[data-testid="stColumn"]:has(.method-b-header-marker) button svg {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 建立「方法 A：追蹤完整文獻脈絡」卡片
    with st.container(border=True):
        col_hdr_a, col_limit = st.columns([7.5, 2.5])
        with col_hdr_a:
            st.markdown('<h4 style="font-size: 16px; font-weight: bold; margin-top: 0; margin-bottom: 8px;">• 方法 A：追蹤完整文獻脈絡</h4>', unsafe_allow_html=True)
            st.markdown("此功能將會下載所有關聯文獻，並建立完整的上下游發展清單。")
        with col_limit:
            fetch_limit = st.number_input("抓取篇數", min_value=1, max_value=100, value=15, step=1)
            
        target_doi = st.text_input("請輸入核心論文 DOI", placeholder="例如：10.1234...", key="doi_input")
        track_btn = st.button("🌐 追蹤全部文獻脈絡", key="track_context", use_container_width=True)

    # 提示與分隔線
    st.markdown("<div style='text-align: center; margin: 18px 0; color: #777; font-size: 13px; font-weight: bold;'>─── 或是您也可以略過上方方法 A，直接使用下方功能 ───</div>", unsafe_allow_html=True)
    
    # 建立「方法 B：AI 精準打擊篩選」卡片
    with st.container(border=True):
        col_hdr, col_info = st.columns([9.2, 0.8])
        with col_hdr:
            st.markdown('<h4 style="font-size: 16px; font-weight: bold; margin-top: 0; margin-bottom: 0;">• 方法 B：AI 精準篩選 Top 10 (推薦)</h4>', unsafe_allow_html=True)
        with col_info:
            st.markdown('<div class="method-b-header-marker"></div>', unsafe_allow_html=True)
            with st.popover("?", help="點擊查看精準篩選操作說明"):
                st.markdown("""
                ### 🎯 AI 精準篩選使用說明
                1. **填寫上方 DOI**：不論使用方法 A 或方法 B，皆須在上方「方法 A」卡片中填入核心論文 DOI。
                2. **輸入過濾關鍵字**：在下方欄位輸入您特別關注的主題（例如：「*實驗動物模型與技術*」或「*神經退化性疾病的臨床應用*」）。
                3. **啟動精準篩選**：點擊下方 **🎯 精準篩選 Top 10** 按鈕。
                4. **檢視 AI 推薦結果**：系統將自動調用 AI 評估所有參考文獻與引用文獻的摘要，並在下方推薦出最相關的各 10 篇上游與下游論文。
                
                *※ 註：此功能需在左側邊欄填寫 Gemini API Key 以啟用 AI 推薦引擎。*
                """)
        
        st.markdown('<div style="margin-top: 8px;"></div>', unsafe_allow_html=True)
        st.markdown("覺得文獻太多嗎？輸入特定關鍵字，讓 AI 直接幫您從上下游文獻中挑出最相關的各 10 篇論文！")
        filter_keyword = st.text_input("輸入過濾關鍵字", placeholder="例如：在神經退化性疾病的臨床應用", label_visibility="collapsed", key="filter_keyword_input")
        strike_btn = st.button("🎯 精準篩選 Top 10", key="strike_context", use_container_width=True)
        
    # 定義一個共用的抓取資料函式
    def fetch_data_if_needed(doi, limit=15):
        # 避免重複抓取相同 DOI
        if 's2_data' in st.session_state and st.session_state.get('current_doi') == doi and st.session_state.get('current_limit') == limit:
            return True
        with st.spinner("正在向 Semantic Scholar 查詢上下游脈絡..."):
            s2_data = backend.fetch_semantic_scholar_context(doi, limit)
            if s2_data:
                st.session_state.s2_data = s2_data
                st.session_state.current_doi = doi
                st.session_state.current_limit = limit
                # DOI 改變了，清除先前暫存的呈現狀態與結果
                st.session_state.pop('show_all_citations', None)
                st.session_state.pop('top10_result', None)
                return True
            else:
                st.error("找不到該文獻的資料。")
                return False

    # 按鈕動作觸發器 (僅修改 session_state)
    if track_btn:
        if not target_doi:
            st.warning("⚠️ 請輸入 DOI！")
        elif fetch_data_if_needed(target_doi, fetch_limit):
            st.session_state.show_all_citations = True

    if strike_btn:
        if not target_doi:
            st.warning("⚠️ 請輸入 DOI！")
        elif not gemini_key:
            st.error("⚠️ 請先在左側邊欄填寫 Gemini API Key！")
        elif not filter_keyword:
            st.warning("⚠️ 請輸入精準篩選的關鍵字！")
        elif fetch_data_if_needed(target_doi, fetch_limit):
            with st.spinner("正在呼叫 Gemini API 進行精準文獻篩選... (約需 10 秒)"):
                top10_result = backend.rank_relevant_papers_llm(
                    filter_keyword,
                    st.session_state.s2_data['references'],
                    st.session_state.s2_data['citations'],
                    gemini_key
                )
                if top10_result:
                    st.session_state.top10_result = top10_result
                else:
                    st.error("篩選失敗，請檢查 API Key 或稍後再試。")

    # 呈現結果區塊 (從 session_state 讀取狀態，確保不會因其他按鈕點擊而消失)
    if 's2_data' in st.session_state:
        s2_data = st.session_state.s2_data
        st.markdown("---")
        st.markdown(f"**核心論文標題：** {s2_data['title']}")
        
        # 建立二級分頁以整合兩種分析視角，保持版面整潔
        tab_all, tab_top10 = st.tabs(["🌐 完整上下游脈絡", "🎯 AI 精準推薦 (Top 10)"])
        
        with tab_all:
            if st.session_state.get('show_all_citations'):
                with st.expander(f"📚 上游參考文獻 (References) - 共 {len(s2_data['references'])} 篇", expanded=True):
                    for i, ref in enumerate(s2_data['references'], 1):
                        url = ref.get('url', '')
                        title = ref.get('title', '無標題')
                        if url:
                            st.markdown(f"{i}. [{title}]({url})")
                        else:
                            st.markdown(f"{i}. {title}")
                            
                with st.expander(f"📈 下游引用文獻 (Citations) - 共 {len(s2_data['citations'])} 篇", expanded=True):
                    for i, cit in enumerate(s2_data['citations'], 1):
                        url = cit.get('url', '')
                        title = cit.get('title', '無標題')
                        if url:
                            st.markdown(f"{i}. [{title}]({url})")
                        else:
                            st.markdown(f"{i}. {title}")
            else:
                st.info("💡 **使用提示**：點擊上方「🌐 追蹤全部文獻脈絡」按鈕，即可在此處展開完整的文獻清單。")
        
        with tab_top10:
            if 'top10_result' in st.session_state:
                top10_result = st.session_state.top10_result
                used_model = top10_result.get('used_model', 'Gemini API')
                st.success(f"✅ AI 篩選完成！為您推薦以下最相關的文獻： (由 **{used_model}** 生成)")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 📚 上游推薦 (References)")
                    top_up_ids = top10_result.get('top_upstream_ids', [])
                    if not top_up_ids:
                        st.info("沒有找到高度相關的上游文獻。")
                    for i, idx in enumerate(top_up_ids, 1):
                        if idx < len(s2_data['references']):
                            p = s2_data['references'][idx]
                            title = p.get('title', '無標題')
                            url = p.get('url', '')
                            if url:
                                st.markdown(f"{i}. [{title}]({url})")
                            else:
                                st.markdown(f"{i}. {title}")
                                
                with col2:
                    st.markdown("#### 📈 下游推薦 (Citations)")
                    top_down_ids = top10_result.get('top_downstream_ids', [])
                    if not top_down_ids:
                        st.info("沒有找到高度相關的下游文獻。")
                    for i, idx in enumerate(top_down_ids, 1):
                        if idx < len(s2_data['citations']):
                            p = s2_data['citations'][idx]
                            title = p.get('title', '無標題')
                            url = p.get('url', '')
                            if url:
                                st.markdown(f"{i}. [{title}]({url})")
                            else:
                                st.markdown(f"{i}. {title}")
            else:
                st.info("💡 **使用提示**：輸入上方過濾關鍵字並點擊「🎯 精準篩選 Top 10」按鈕，AI 將在此處顯示推薦結果。")
                
        if track_btn:
            st.components.v1.html(
                """
                <script>
                    var tabs = window.parent.document.querySelectorAll('div[data-testid="stTabs"]');
                    if (tabs.length > 0) {
                        tabs[tabs.length - 1].scrollIntoView({behavior: "smooth"});
                    }
                </script>
                """,
                height=0
            )

    if 's2_data' in st.session_state:
        st.markdown("---")
        st.markdown("### AI 脈絡總結")
        
        context_focus = st.text_area(
            "您特別想關注的關鍵知識點（選填）", 
            placeholder="例如：請專注於討論 GluRδ2 蛋白的相關技術與機制",
            help="若輸入此欄位，AI 將戴上『過濾眼鏡』，專注於從上下游文獻中為您尋找與此知識點相關的脈絡。"
        )
        
        if st.button("✨ 執行 AI 脈絡歸納", key="run_context"):
            if not gemini_key:
                st.error("⚠️ 請先在左側邊欄填寫 Gemini API Key！")
            else:
                with st.spinner("正在呼叫 Gemini API 分析學術脈絡..."):
                    context_result = backend.analyze_citation_context(
                        st.session_state.s2_data['title'], 
                        st.session_state.s2_data['references'], 
                        st.session_state.s2_data['citations'], 
                        gemini_key,
                        focus_query=context_focus
                    )
                    
                    if context_result:
                        match = re.search(r"<!-- MODEL:(.*?) -->", context_result)
                        used_model = match.group(1) if match else "Gemini API"
                        context_result = re.sub(r"<!-- MODEL:(.*?) -->\n", "", context_result)
                        
                        st.success(f"✅ AI 脈絡分析完成！(由 **{used_model}** 生成)")
                        st.markdown(context_result)

# ------------------------------------------
# 分頁三：單篇文獻精讀 (Deep Read)
# ------------------------------------------
with tab3:
    st.subheader("單篇文獻精讀 (Deep Read)")
    st.markdown("針對生醫領域研究設計！利用 PMC 全文開放存取資源，為您拆解「逐圖邏輯」故事線，並提供「批判性思考」輔助分析（研究限制與未來方向）。")
    
    # 輸入區塊
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        # 預填 tab2 的 DOI（如果有）
        default_id = st.session_state.get('doi_input', '')
        deep_read_id = st.text_input(
            "請輸入論文 DOI、PMID 或 PMCID", 
            value=default_id, 
            placeholder="例如：10.1234/abcd.5678 或 32439832", 
            key="deep_read_id_input",
            help="支援直接輸入 DOI (例如 10.1234/abcd.5678)、PMID (例如 32439832) 或 PMCID (例如 PMC7299136)"
        )
    with col_btn:
        # 加點 padding 讓按鈕與輸入框對齊
        st.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
        deep_read_clicked = st.button("🔬 啟動 AI 單篇精讀", key="run_deep_read", use_container_width=True, type="primary")

    # 點擊按鈕觸發
    if deep_read_clicked:
        if not user_email:
            st.error("⚠️ 請先在左側邊欄填寫聯絡信箱！")
        elif not deep_read_id:
            st.warning("⚠️ 請輸入論文識別碼 (DOI, PMID 或 PMCID)！")
        elif not gemini_key:
            st.error("⚠️ 請先在左側邊欄填寫 Gemini API Key！")
        else:
            with st.status("🔍 正在抓取與精讀文獻...", expanded=True) as status:
                model_indicator = st.empty()
                st.write("📥 正在抓取文獻全文與圖表資訊...")
                doc_data = backend.fetch_pmc_fulltext_and_figures(deep_read_id, user_email)
                
                if doc_data:
                    st.session_state.deep_read_data = doc_data
                    
                    # 進行 AI 逐圖邏輯分析 (強制重新載入模組，簡化錯誤訊息)
                    status.update(label="稍等稍等~正在拆解 Figure 邏輯...", state="running")
                    st.write("🧠 呼叫 AI 進行「逐圖邏輯 (Figure-by-Figure Logic)」故事線分析...")
                    fig_logic = backend.analyze_figure_logic(
                        doc_data['title'],
                        doc_data['abstract'],
                        doc_data['figures'],
                        gemini_key
                    )
                    if fig_logic:
                        st.session_state.deep_read_fig_logic = fig_logic
                    else:
                        st.error("⚠️ 逐圖邏輯分析生成失敗，可能是 API 額度耗盡或網路連線問題。")
                        
                    # 進行 AI 批判性思考分析
                    status.update(label="等等ㄛ正在排版中...", state="running")
                    st.write("🕵️ 呼叫 AI 進行「批判性思考輔助 (Limitations & Next Steps)」分析...")
                    crit_thinking = backend.analyze_limitations_and_future(
                        doc_data['title'],
                        doc_data['abstract'],
                        doc_data['discussion'],
                        gemini_key
                    )
                    if crit_thinking:
                        st.session_state.deep_read_crit_thinking = crit_thinking
                    else:
                        st.error("⚠️ 批判性思考分析生成失敗，可能是 API 額度耗盡或網路連線問題。")
                        
                    if fig_logic and crit_thinking:
                        # 抽出模型名稱並放在最上方的 model_indicator
                        match = re.search(r"<!-- MODEL:(.*?) -->", fig_logic)
                        used_model = match.group(1) if match else "Gemini API"
                        model_indicator.success(f"💡 本次分析由 **{used_model}** 生成")
                        
                        # 清除文字中的標籤
                        st.session_state.deep_read_fig_logic = re.sub(r"<!-- MODEL:(.*?) -->\n", "", fig_logic)
                        st.session_state.deep_read_crit_thinking = re.sub(r"<!-- MODEL:(.*?) -->\n", "", crit_thinking)
                        
                        status.update(label="✅ 單篇精讀分析完成！", state="complete", expanded=False)
                    else:
                        status.update(label="❌ 分析未完全成功，部分結果未能生成", state="error", expanded=True)
                else:
                    status.update(label="❌ 抓取失敗", state="error", expanded=False)
                    st.error("無法抓取該文獻的資料，請確認識別碼是否正確，或該文獻是否存在於 PubMed/PMC 資料庫。")

    # 呈現結果 (讀取 session_state，確保在切換 Tab 時不遺失)
    if 'deep_read_data' in st.session_state:
        doc_data = st.session_state.deep_read_data
        
        st.markdown("---")
        col_title, col_export = st.columns([4, 1])
        with col_title:
            st.markdown(f"### 📄 精讀文獻：{doc_data['title']}")
        with col_export:
            export_content = f"# {doc_data['title']}\\n\\n## 逐圖邏輯故事線\\n\\n{st.session_state.get('deep_read_fig_logic', '')}\\n\\n## 批判性思考輔助\\n\\n{st.session_state.get('deep_read_crit_thinking', '')}"
            if 'qa_history' in st.session_state and st.session_state.qa_history:
                export_content += "\\n\\n## 延伸問答紀錄\\n\\n"
                for qa in st.session_state.qa_history:
                    export_content += f"**Q:** {qa['q']}\\n\\n**A:** {qa['a']}\\n\\n"
            
            with st.popover("📥 匯出筆記", use_container_width=True):
                st.markdown("選擇您需要的格式：")
                st.download_button("📝 下載為純文字 (.txt)", data=export_content, file_name="deep_read_notes.txt", mime="text/plain", use_container_width=True, help="適合直接閱讀或貼入 Word")
                st.download_button("💻 下載為 Markdown (.md)", data=export_content, file_name="deep_read_notes.md", mime="text/markdown", use_container_width=True, help="適合 Notion 或 Obsidian 用戶")
        
        # 降級警告 (若 has_fulltext 爲 False)
        if not doc_data.get('has_fulltext', True):
            st.warning("⚠️ 提醒：本論文不具備 PMC 全文開放存取權限 (Open Access)，系統已自動降級至「僅以摘要分析」模式。")

        # 雙欄位佈局，顯示分析結果
        col_left, col_right = st.columns(2)
        
        with col_left:
            with st.container(border=True):
                st.markdown('<h4 style="color: #4A4A8A; border-bottom: 2px solid #E6E6FA; padding-bottom: 5px; margin-top: 0;">📊 逐圖邏輯故事線 (Figure Storyline)</h4>', unsafe_allow_html=True)
                if 'deep_read_fig_logic' in st.session_state and st.session_state.deep_read_fig_logic:
                    st.markdown(st.session_state.deep_read_fig_logic, unsafe_allow_html=True)
                    
                    # 擷取專有名詞並建立按鈕
                    terms = re.findall(r'<span title="[^"]*"[^>]*>(.*?)</span>', st.session_state.deep_read_fig_logic)
                    terms = list(dict.fromkeys(terms)) # 去除重複
                    if terms:
                        st.markdown("<br><b>📖 深度名詞解析 (點擊查詢)</b>", unsafe_allow_html=True)
                        selected_term = st.pills("選擇名詞", options=terms, selection_mode="single", key="fig_terms_pills", label_visibility="collapsed")
                        if selected_term:
                            if gemini_key:
                                show_term_dialog(selected_term, gemini_key)
                            else:
                                st.error("請先於側邊欄填寫 Gemini API Key！")
                else:
                    st.info("尚未生成分析結果。")
                    
        with col_right:
            with st.container(border=True):
                st.markdown('<h4 style="color: #8B4A4A; border-bottom: 2px solid #FFE4E1; padding-bottom: 5px; margin-top: 0;">🧠 批判性思考輔助 (Limitations & Next Steps)</h4>', unsafe_allow_html=True)
                if 'deep_read_crit_thinking' in st.session_state and st.session_state.deep_read_crit_thinking:
                    st.markdown(st.session_state.deep_read_crit_thinking, unsafe_allow_html=True)
                    
                    # 擷取專有名詞並建立按鈕
                    crit_terms = re.findall(r'<span title="[^"]*"[^>]*>(.*?)</span>', st.session_state.deep_read_crit_thinking)
                    crit_terms = list(dict.fromkeys(crit_terms))
                    if crit_terms:
                        st.markdown("<br><b>📖 深度名詞解析 (點擊查詢)</b>", unsafe_allow_html=True)
                        selected_crit = st.pills("選擇名詞", options=crit_terms, selection_mode="single", key="crit_terms_pills", label_visibility="collapsed")
                        if selected_crit:
                            if gemini_key:
                                show_term_dialog(selected_crit, gemini_key)
                            else:
                                st.error("請先於側邊欄填寫 Gemini API Key！")
                else:
                    st.info("尚未生成分析結果。")
                    
        st.markdown("---")
        st.markdown('<h4 style="color: #2F4F4F;">💬 進階探索 (Deep Read Q&A)</h4>', unsafe_allow_html=True)
        
        # 顯示歷史問答
        if 'qa_history' not in st.session_state:
            st.session_state.qa_history = []
            
        for qa in st.session_state.qa_history:
            with st.chat_message("user"):
                st.markdown(qa['q'])
            with st.chat_message("assistant"):
                st.markdown(qa['a'], unsafe_allow_html=True)
                
        # 聊天輸入框
        if question := st.chat_input("對這篇文獻有疑問嗎？例如：這篇的活體光遺傳學刺激頻率是設多少？"):
            if not gemini_key:
                st.error("⚠️ 請先在左側邊欄填寫 Gemini API Key！")
            else:
                with st.chat_message("user"):
                    st.markdown(question)
                    
                with st.chat_message("assistant"):
                    with st.spinner("AI 正在翻閱文獻尋找答案..."):
                        answer = backend.analyze_paper_qa(doc_data, question, gemini_key)
                    
                    if answer:
                        if "[NOT_MENTIONED]" in answer:
                            clean_answer = answer.replace("[NOT_MENTIONED]", "").strip()
                            st.markdown(clean_answer, unsafe_allow_html=True)
                            st.info("💡 這個問題似乎超出了本文探討的範圍。要不要去「脈絡追蹤」找找看有沒有相關研究解答了這個問題？")
                            if st.button("🌐 點我一鍵前往 [脈絡追蹤] 尋找相關下游文獻", key=f"redirect_tab2_{len(st.session_state.qa_history)}"):
                                st.session_state.doi_input = doc_data.get('doi', deep_read_id)
                                st.success("✅ 已為您將 DOI 填入，請點擊上方『🌐 脈絡追蹤 (Semantic Scholar)』分頁開始檢索！")
                        else:
                            st.markdown(answer, unsafe_allow_html=True)
                            
                        st.session_state.qa_history.append({"q": question, "a": answer.replace("[NOT_MENTIONED]", "").strip()})

