import ssl
import requests
import ipaddress
import time
import sys
from Bio import Entrez
import google.generativeai as genai
import streamlit as st

# 加入這行「魔法指令」，讓 Python 信任連線，不強制檢查 SSL 憑證
ssl._create_default_https_context = ssl._create_unverified_context

def is_public_ip_ntu_range(client_ip=None):
    """
    檢查目前的對外 Public IP 是否屬於台大網段 (140.112.0.0/16)。
    若傳入 client_ip，則直接驗證該 IP；否則呼叫免費 API 獲取伺服器目前的 IP。
    """
    try:
        if client_ip:
            ip_str = client_ip
        else:
            # 呼叫免費 API 獲取目前的 Public IP
            response = requests.get("https://api.ipify.org?format=json", timeout=5)
            response.raise_for_status()
            ip_str = response.json().get("ip")
        
        current_ip = ipaddress.ip_address(ip_str)
        if isinstance(current_ip, ipaddress.IPv4Address):
            ntu_network = ipaddress.IPv4Network("140.112.0.0/16")
            return current_ip in ntu_network
        else:
            ntu_network_v6 = ipaddress.IPv6Network("2001:288:2000::/36")
            return current_ip in ntu_network_v6
            
    except Exception as e:
        print(f"IP 檢查失敗: {e}")
        return False

def search_pubmed_titles_abstracts(query, email, max_results=10):
    """
    使用 Biopython 搜尋 PubMed，並回傳論文的標題與摘要。
    回傳格式: [{'title': '...', 'abstract': '...'}, ...]
    """
    # NCBI 要求必須提供 email
    Entrez.email = email
    
    try:
        # 第一步：用關鍵字搜尋，取得論文的 ID 列表
        print(f"正在搜尋 PubMed 關鍵字: '{query}'...")
        search_handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results, sort="relevance")
        search_results = Entrez.read(search_handle)
        search_handle.close()
        
        id_list = search_results.get("IdList", [])
        if not id_list:
            print("找不到相關文章。")
            return []
            
        print(f"找到 {len(id_list)} 篇文獻，正在下載摘要...")
        
        # 第二步：用這些 ID 去抓取詳細的 XML 資料
        fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
        papers = Entrez.read(fetch_handle)
        fetch_handle.close()
        
        # 第三步：整理資料
        extracted_data = []
        for paper in papers['PubmedArticle']:
            article = paper['MedlineCitation']['Article']
            
            # 抓取標題
            title = article.get('ArticleTitle', '無標題')
            
            # 抓取摘要 (有些摘要是分段的，需要合併起來)
            abstract_text = '無摘要'
            if 'Abstract' in article and 'AbstractText' in article['Abstract']:
                abstract_list = article['Abstract']['AbstractText']
                abstract_text = " ".join([str(text) for text in abstract_list])
                
            # 抓取期刊名稱
            journal = article.get('Journal', {})
            journal_name = str(journal.get('ISOAbbreviation') or journal.get('Title') or '未知期刊')
            
            # 抓取 DOI
            doi = ''
            pubmed_data = paper.get('PubmedData', {})
            article_id_list = pubmed_data.get('ArticleIdList', [])
            for aid in article_id_list:
                if getattr(aid, 'attributes', {}).get('IdType') == 'doi':
                    doi = str(aid)
                    break
            
            if not doi:
                elocation_ids = article.get('ELocationID', [])
                for eid in elocation_ids:
                    if getattr(eid, 'attributes', {}).get('EIdType') == 'doi':
                        doi = str(eid)
                        break
                
            extracted_data.append({
                'title': title,
                'abstract': abstract_text,
                'journal': journal_name,
                'doi': doi
            })
            
        return extracted_data

    except Exception as e:
        print(f"抓取 PubMed 資料時發生錯誤: {e}")
        return []

def fetch_semantic_scholar_context(doi, limit=15):
    """
    使用 Semantic Scholar Graph API，透過 DOI 獲取該篇論文的：
    1. 上游參考文獻 (References)
    2. 下游引用文獻 (Citations)
    """
    # 自動清理使用者輸入的 DOI，避免因為多複製了 "DOI:" 或網址而導致錯誤
    doi = doi.strip()
    if doi.lower().startswith("doi:"):
        doi = doi[4:].strip()
    elif doi.startswith("https://doi.org/"):
        doi = doi[16:].strip()
        
    print(f"正在向 Semantic Scholar 查詢 DOI: {doi} 的上下游脈絡...")
    
    # 這裡的 fields 指定了我們想要 API 回傳哪些資料
    # 我們要求回傳這篇論文的標題、摘要，以及它的 references 和 citations 的標題、摘要與網址 (並加入 externalIds 取得 DOI)
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract,references.title,references.abstract,references.url,references.externalIds,citations.title,citations.abstract,citations.url,citations.externalIds"
    
    try:
        # 加入微秒級延遲，防封鎖策略 (實作企劃書中提到的 Rate Limiting 控制)
        time.sleep(0.5) 
        
        response = requests.get(url, timeout=10)
        response.raise_for_status() # 如果發生 4xx 或 5xx 錯誤，會直接跳到 except
        
        data = response.json()
        
        # 處理參考文獻與引用的 URL，優先使用 DOI 直接跳轉期刊
        def process_paper_url(paper_list):
            if not paper_list:
                return []
            for paper in paper_list:
                ext_ids = paper.get('externalIds') or {}
                # 如果有 DOI，就替換為 doi.org 的網址
                if 'DOI' in ext_ids:
                    paper['url'] = f"https://doi.org/{ext_ids['DOI']}"
            return paper_list
            
        # 整理我們要回傳的資料
        result = {
            'title': data.get('title') or '無標題',
            'abstract': data.get('abstract') or '無摘要',
            'references': process_paper_url(data.get('references'))[:limit], # 上游文獻，確保不會是 None
            'citations': process_paper_url(data.get('citations'))[:limit]    # 下游文獻，確保不會是 None
        }
        
        # 實作 OpenAlex 備用資料庫機制
        if len(result['references']) == 0:
            print("[警告] Semantic Scholar 找不到上游文獻 (可能受版權限制)，啟動 OpenAlex 備用資料庫...")
            openalex_refs = fetch_openalex_fallback(doi, limit)
            result['references'] = openalex_refs
        
        print(f"成功抓取！找到 {len(result['references'])} 篇上游文獻，{len(result['citations'])} 篇下游文獻。")
        return result
        
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 404:
            print(f"[警告] 找不到該 DOI ({doi}) 的資料，可能 Semantic Scholar 尚未收錄。")
        elif response.status_code == 429:
            print(f"[警告] 請求太過頻繁 (429 Too Many Requests)，請稍後再試或考慮加上 API Key。")
        else:
            print(f"HTTP 錯誤: {http_err}")
        return None
    except Exception as e:
        print(f"抓取 Semantic Scholar 資料時發生錯誤: {e}")
        return None

def fetch_openalex_fallback(doi, limit=None):
    """
    當 Semantic Scholar 無法取得 Reference 時的備用機制。
    使用 OpenAlex API 獲取上游文獻標題。
    """
    try:
        # 第一步：先取得這篇論文的 OpenAlex 資訊
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        referenced_ids = data.get('referenced_works', [])
        
        if not referenced_ids:
            return []
            
        if limit:
            referenced_ids = referenced_ids[:limit]
            
        print(f"[進度] OpenAlex 找到 {len(referenced_ids)} 篇上游文獻，正在獲取標題...")
        
        # 第二步：批次拿取這些 referenced_works 的標題 (OpenAlex 支援用 | 分隔批量查詢)
        # 為了避免 URL 太長，我們一次最多查 50 篇
        batch_size = 50
        fetched_references = []
        
        for i in range(0, len(referenced_ids), batch_size):
            batch_ids = referenced_ids[i:i+batch_size]
            # 取出 OpenAlex ID (如 https://openalex.org/Wxxx -> Wxxx)
            short_ids = [ref_url.split('/')[-1] for ref_url in batch_ids]
            
            filter_str = "|".join(short_ids)
            batch_url = f"https://api.openalex.org/works?filter=openalex:{filter_str}&select=title,doi"
            
            batch_response = requests.get(batch_url, timeout=10)
            if batch_response.status_code == 200:
                results = batch_response.json().get('results', [])
                for work in results:
                    fetched_references.append({
                        'title': work.get('title') or '無標題',
                        'abstract': '無摘要', # OpenAlex 摘要需要解碼 Inverted Index，此處以抓標題為主
                        'url': work.get('doi') or '' # 嘗試取得 doi 當作網址
                    })
                    
            time.sleep(0.5) # 防止被 OpenAlex 擋掉
            
        return fetched_references
        
    except Exception as e:
        print(f"OpenAlex 備用抓取失敗: {e}")
        return []

@st.cache_data(ttl=3600)
def call_gemini_with_fallback(prompt, api_key, _generation_config=None):
    """
    呼叫 Gemini API，支援多個模型（gemini-3.1-pro-preview, gemini-2.5-pro, gemini-3.5-flash, gemini-2.5-flash, gemini-2.0-flash）依序遞補與 Rate Limit 延遲重試。
    """
    import time
    if not api_key:
        return None
    
    models_to_try = ['gemini-2.5-pro', 'gemini-3.1-pro-preview', 'gemini-2.5-flash', 'gemini-3.5-flash', 'gemini-2.0-flash']
    
    for model_name in models_to_try:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            # 關閉安全性設定以避免生物醫學專有名詞被誤判阻擋
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            for attempt in range(3):
                try:
                    print(f"嘗試使用模型 {model_name} (第 {attempt+1} 次)...")
                    import streamlit as st
                    st.markdown(f'<p style="font-size: 13px; margin: 0px 0px 2px 0px; color: #555;">⏳ 正在嘗試使用模型：{model_name} ...</p>', unsafe_allow_html=True)
                    
                    if _generation_config:
                        response = model.generate_content(prompt, generation_config=_generation_config, safety_settings=safety_settings)
                    else:
                        response = model.generate_content(prompt, safety_settings=safety_settings)
                    
                    if response and response.text:
                        # 插入隱藏的 HTML 註解，讓前端 (app.py) 可以抓到使用的是哪個模型
                        return f"<!-- MODEL:{model_name} -->\n" + response.text
                    else:
                        raise Exception("Gemini 回傳了空的內容。")
                except Exception as e:
                    err_str = str(e)
                    import streamlit as st
                    
                    # 檢查是否為需要付費的硬性限制
                    is_billing_issue = any(k in err_str.lower() for k in ["billing", "check your plan"])
                    if is_billing_issue:
                        st.markdown(f'<p style="font-size: 12px; margin: 0px 0px 8px 0px; color: #999;">⚠️ {model_name} 屬於付費模型，將直接跳過。</p>', unsafe_allow_html=True)
                        raise Exception(f"模型 {model_name} 需綁定信用卡，無法使用。")
                        
                    # 將所有 quota/rate limit 錯誤視為可換模型重試的錯誤
                    is_rate_limit = any(k in err_str.lower() for k in ["429", "quota", "exhausted", "rate limit"])
                    if is_rate_limit:
                        if attempt < 2:
                            print(f"模型 {model_name} 暫時受限 (429/Quota): {err_str[:30]}。等待 3 秒後重試...")
                            time.sleep(3)
                        else:
                            raise Exception(f"模型 {model_name} 已達最大重試次數，仍被限流。")
                    else:
                        raise e
                        
        except Exception as e:
            err_msg = str(e)
            print(f"使用模型 {model_name} 失敗: {err_msg}。將嘗試下一個備用模型...")
            import streamlit as st
            
            # 一般錯誤，可選擇是否每個都顯示，這裡改為不逐一顯示 st.error，只在最後統整
            
            # 如果是找不到模型的錯誤，印出該金鑰實際能用的模型清單
            if "404" in err_msg and "not found" in err_msg:
                try:
                    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    st.info(f"💡 您的 API Key 支援的模型清單: {', '.join(available_models)}")
                except Exception as ex:
                    pass
            continue
            
    print("❌ 所有 Gemini 模型皆無法正常呼叫（可能 API 金鑰無效或所有模型皆超出額度）。")
    import streamlit as st
    st.error("所有 AI 模型均呼叫失敗。可能是因為 API 額度耗盡，或金鑰無效。")
    return None

@st.cache_data(ttl=3600)
def translate_abstract_with_tooltips(abstract, api_key):
    """
    使用 Gemini 翻譯摘要，並針對醫學專有名詞加上 HTML 懸浮提示 (Tooltip)。
    強制鎖定使用 gemini-2.5-flash。
    """
    import google.generativeai as genai
    import streamlit as st
    if not api_key:
        return "⚠️ 尚未提供 API Key"
        
    prompt = f"""
請將以下生醫論文的英文摘要翻譯成流暢的繁體中文。
【重要指令】：
在翻譯過程中，如果你遇到「醫學專有名詞」、「特殊疾病名稱」、「罕見技術」或「生物標記」等專業詞彙，
請在輸出翻譯時，使用 HTML 的 <span> 標籤將該中文詞彙包覆起來，並在 title 屬性中提供該詞彙的詳細解釋。

格式範例：
我們使用了<span title="一種利用螢光物質標記抗體來檢測細胞內特定蛋白質的技術" style="border-bottom: 1px dashed gray; cursor: help; color: #1f77b4; font-weight: bold;">免疫螢光染色法</span>來觀察細胞。

請務必：
1. 翻譯要精確且符合台灣生醫領域的用語習慣。
2. 不要改變原本摘要的段落結構。
3. 只回傳翻譯後的 HTML 文本，不要包含任何 markdown 程式碼區塊符號 (例如 ```html)。

摘要原文：
{abstract}
    """
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        st.markdown('<p style="font-size: 13px; margin: 0px 0px 2px 0px; color: #555;">⏳ 正在呼叫 gemini-2.5-flash 進行智能翻譯...</p>', unsafe_allow_html=True)
        response = model.generate_content(prompt, safety_settings=safety_settings)
        
        if response and response.text:
            text = response.text
            if text.startswith("```html"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            return text.strip()
        return "⚠️ 翻譯失敗，回傳內容為空。"
    except Exception as e:
        return f"⚠️ 翻譯時發生錯誤: {e}"

@st.cache_data(ttl=3600)
def analyze_papers_clustering(papers_data, focus_dimension, api_key):
    """
    使用 Gemini API 對文獻進行自訂維度的語義分群。
    """
    if not api_key:
        print("⚠️ 未提供 Gemini API Key，跳過 LLM 分析。")
        return None
        
    papers_text = ""
    for i, p in enumerate(papers_data, 1):
        abstract = p.get('abstract') or '無摘要'
        papers_text += f"[{i}] 標題: {p.get('title')}\n摘要: {abstract}\n\n"
        
    prompt = f"""
請你扮演一位學術界資深研究員。
以下是幾篇文獻的標題與摘要：
{papers_text}

請根據以下使用者自訂的焦點維度來進行分群：【{focus_dimension}】

請依照這個維度，將這些文獻分成幾個群組（如果無法分類可列為「其他」）。
針對每一篇文獻，請用一句話總結它的「實驗亮點」或「關鍵發現」。
回傳格式請盡量清晰、排版易讀。
"""
    print(f"正在呼叫 Gemini API 進行語義分群分析 (維度: {focus_dimension})...")
    return call_gemini_with_fallback(prompt, api_key)

def analyze_citation_context(core_title, upstream_papers, downstream_papers, api_key, focus_query=""):
    """
    使用 Gemini API 歸納單一研究的上游理論與下游發展趨勢。
    若提供 focus_query，則 LLM 會專注於萃取跟該知識點相關的資訊。
    """
    if not api_key:
        print("[警告] 未提供 Gemini API Key，跳過 LLM 分析。")
        return None
        
    upstream_text = "\n".join([f"- {p.get('title')}: {p.get('abstract')}" for p in upstream_papers[:15]])
    downstream_text = "\n".join([f"- {p.get('title')}: {p.get('abstract')}" for p in downstream_papers[:15]])
    
    focus_prompt = ""
    if focus_query.strip():
        focus_prompt = f"\n[特別指令]：使用者特別想知道與「{focus_query}」相關的資訊，請你嚴格聚焦在這個知識點上，從上下游文獻中萃取相關的技術與機制，過濾掉無關的雜訊！\n"
        
    prompt = f"""
請你扮演生醫領域專家，分析這篇核心論文的學術脈絡。
{focus_prompt}
核心論文標題：{core_title}

這篇核心論文的「上游參考文獻」如下：
{upstream_text}

這篇核心論文的「下游引用文獻」如下：
{downstream_text}

請你根據這些文獻，進行脈絡歸納：
1. 【理論基礎】：從上游文獻中，歸納出這篇核心論文是基於什麼樣的歷史技術或理論基礎發展出來的？
2. 【未來趨勢】：從下游文獻中，總結出這篇核心論文發表後，後續的科學家如何改良這項技術或應用在什麼新領域？
請用簡潔專業的段落回覆。
"""
    print("正在呼叫 Gemini API 進行脈絡分析...")
    return call_gemini_with_fallback(prompt, api_key)

import json

def rank_relevant_papers_llm(keyword, upstream_papers, downstream_papers, api_key):
    """
    使用 Gemini API 根據使用者的關鍵字，挑選出最相關的 Top 10 上下游文獻。
    回傳格式為 JSON dict，包含 top_upstream_ids 與 top_downstream_ids 陣列。
    """
    if not api_key:
        print("[警告] 未提供 Gemini API Key，跳過 LLM 分析。")
        return None
        
    upstream_json = [{"id": i, "title": p.get('title'), "abstract": p.get('abstract')} for i, p in enumerate(upstream_papers)]
    downstream_json = [{"id": i, "title": p.get('title'), "abstract": p.get('abstract')} for i, p in enumerate(downstream_papers)]
    
    prompt = f"""
使用者正在研究一篇核心論文，並希望找到與特定主題最相關的上下游文獻。
使用者給定的過濾關鍵字/句子是：「{keyword}」

這是上游參考文獻清單 (JSON格式)：
{json.dumps(upstream_json, ensure_ascii=False)}

這是下游引用文獻清單 (JSON格式)：
{json.dumps(downstream_json, ensure_ascii=False)}

請根據使用者的過濾關鍵字，從上游挑選出「最相關」的不超過 10 篇文獻，以及從下游挑選出「最相關」的不超過 10 篇文獻，並依照相關程度由高到低排序。
請務必嚴格使用 JSON 格式回傳，格式如下：
{{
  "top_upstream_ids": [整數ID1, 整數ID2...],
  "top_downstream_ids": [整數ID1, 整數ID2...]
}}
請確保除了 JSON 之外不要輸出任何文字。
"""
    try:
        print("正在呼叫 Gemini API 進行精準文獻篩選...")
        res_text = call_gemini_with_fallback(prompt, api_key, _generation_config={"response_mime_type": "application/json"})
        if res_text:
            import re
            # 將隱藏的模型標籤抽出來，避免破壞 JSON 格式
            match = re.search(r"<!-- MODEL:(.*?) -->\n", res_text)
            model_name = match.group(1) if match else "Gemini"
            clean_json = re.sub(r"<!-- MODEL:(.*?) -->\n", "", res_text)
            
            data = json.loads(clean_json)
            data['used_model'] = model_name
            return data
        return None
    except Exception as e:
        print(f"呼叫 Gemini API 篩選文獻時發生錯誤: {e}")
        return None

def fetch_pmc_fulltext_and_figures(identifier, email):
    """
    用 DOI 或 PMID/PMCID 查詢 PMC 並取得全文結構 (包含圖表與 Discussion)。
    """
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    Entrez.email = email
    
    identifier = identifier.strip()
    if identifier.lower().startswith("doi:"):
        identifier = identifier[4:].strip()
    elif identifier.startswith("https://doi.org/"):
        identifier = identifier[16:].strip()
        
    try:
        # 1. 搜尋 PMC ID
        if '/' in identifier or identifier.startswith("10."):
            term = f"{identifier}[DOI]"
        else:
            clean_id = identifier.lower()
            if clean_id.startswith("pmc"):
                clean_id = clean_id[3:]
            elif clean_id.startswith("pmid"):
                clean_id = clean_id[4:]
            term = f"{clean_id}[PMID]"
            
        print(f"正在搜尋 PMC, 關鍵字: {term}...")
        search_handle = Entrez.esearch(db="pmc", term=term)
        search_record = Entrez.read(search_handle)
        search_handle.close()
        
        id_list = search_record.get("IdList", [])
        if not id_list:
            # 試著去 PubMed 拿 Abstract 作為 Fallback
            print(f"[警告] PMC 中找不到該文獻 ({identifier}) 的全文。")
            if '/' in identifier or identifier.startswith("10."):
                term_pub = f"{identifier}[DOI]"
            else:
                term_pub = clean_id
            pub_handle = Entrez.esearch(db="pubmed", term=term_pub)
            pub_record = Entrez.read(pub_handle)
            pub_handle.close()
            pub_ids = pub_record.get("IdList", [])
            if pub_ids:
                fetch_handle = Entrez.efetch(db="pubmed", id=pub_ids[0], retmode="xml")
                papers = Entrez.read(fetch_handle)
                fetch_handle.close()
                if papers['PubmedArticle']:
                    article = papers['PubmedArticle'][0]['MedlineCitation']['Article']
                    title = article.get('ArticleTitle', '無標題')
                    abstract_text = '無摘要'
                    if 'Abstract' in article and 'AbstractText' in article['Abstract']:
                        abstract_text = " ".join([str(text) for text in article['Abstract']['AbstractText']])
                    return {
                        'title': title,
                        'abstract': abstract_text,
                        'figures': [],
                        'discussion': '無法取得討論區段，本論文不具備 PMC 全文開放存取權限。',
                        'has_fulltext': False
                    }
            return None
            
        pmcid = id_list[0]
        print(f"找到 PMC ID: {pmcid}，正在獲取全文 XML...")
        # 2. 獲取 PMC XML 全文
        fetch_handle = Entrez.efetch(db="pmc", id=pmcid, retmode="xml")
        xml_data = fetch_handle.read()
        fetch_handle.close()
        
        # 3. 解析 XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_data)
        
        # 取得標題
        title_node = root.find('.//article-title')
        title = "".join(title_node.itertext()).strip() if title_node is not None else '無標題'
        
        # 取得摘要
        abstract_nodes = root.findall('.//abstract//p')
        if abstract_nodes:
            abstract_text = "\n".join(["".join(p.itertext()).strip() for p in abstract_nodes])
        else:
            abstract_node = root.find('.//abstract')
            abstract_text = "".join(abstract_node.itertext()).strip() if abstract_node is not None else '無摘要'
        
        # 提取圖表說明
        figures = []
        figs = root.findall('.//fig')
        for fig in figs:
            label = fig.find('.//label')
            caption = fig.find('.//caption')
            label_txt = "".join(label.itertext()).strip() if label is not None else 'Fig'
            caption_txt = "".join(caption.itertext()).strip() if caption is not None else '無說明'
            caption_txt = " ".join(caption_txt.split())
            figures.append({
                'label': label_txt,
                'caption': caption_txt
            })
            
        # 提取 Discussion 段落
        discussion_paragraphs = []
        secs = root.findall('.//sec')
        for sec in secs:
            title_node = sec.find('title')
            if title_node is not None and title_node.text and 'discussion' in title_node.text.lower():
                paragraphs = sec.findall('.//p')
                for p in paragraphs:
                    discussion_paragraphs.append("".join(p.itertext()).strip())
                    
        discussion_text = "\n\n".join(discussion_paragraphs)
        
        # 如果討論段落太少，fallback 到整篇 body
        if len(discussion_text) < 100:
            body_node = root.find('.//body')
            if body_node is not None:
                discussion_text = " ".join("".join(body_node.itertext()).split())[:8000]
                
        return {
            'title': title,
            'abstract': abstract_text,
            'figures': figures,
            'discussion': discussion_text,
            'has_fulltext': True
        }
        
    except Exception as e:
        print(f"PMC 抓取失敗: {e}")
        return None

def analyze_figure_logic(title, abstract, figures, api_key):
    """
    使用 Gemini API 對文獻進行「逐圖邏輯」故事線歸納。
    """
    if not api_key:
        print("⚠️ 未提供 Gemini API Key，跳過 LLM 分析。")
        return None
        
    if figures:
        figs_text = ""
        for fig in figures:
            figs_text += f"- **{fig.get('label', 'Fig')}**: {fig.get('caption', '無說明')}\n"
    else:
        figs_text = "（本論文無 PMC 全文圖表說明資料，請依據摘要進行推導）"
        
    prompt = f"""
請扮演一位頂尖的生醫領域博士後研究員（但請勿在輸出中提及此設定）。我會提供論文的標題、摘要與圖表說明，請為我整理這篇論文的報告內容（請勿在輸出中提及「Journal Club」或「簡報/報告」等字眼）。

論文標題：{title}
摘要：{abstract}

圖表清單與說明：
{figs_text}

請根據以下結構來組織您的輸出：
1. **綜合摘要**：在最開頭提供一段精簡的綜合敘述，必須包含「實驗背景」與「精簡結果摘要」。
2. **逐圖邏輯 (Figure-by-Figure)**：接著依序列出每個 Figure 的核心發現，還原整篇研究的故事線。
   - 針對每個 Figure，**請先用粗體寫出 1 到 2 句話的該圖核心摘要**（例如：**Figure 1 證明了某某蛋白在疾病中的表現量下降。**）。
   - 接著在下方以條列式詳細說明該圖的實驗邏輯與發現。
   - 請不要在段落結尾或任何地方加上藍色箭頭 (➡️) 符號，保持排版乾淨。

輸出請使用繁體中文（台灣學術常用語）以 Markdown 格式呈現，保持精簡、專業，並強調文中所使用的實驗技術與模型（例如：光遺傳學、特定基因敲除小鼠、斑馬魚模型、西方墨點法、免疫組織化學染色等）。
若在輸出中包含生醫重要專有名詞或縮寫（如 VTA、DREADDs 等），請自動加上 HTML 懸停提示語法，例如：`<span title="此處填寫簡短的中文解釋" style="border-bottom: 1px dotted #888; cursor: help;">專有名詞</span>`，讓使用者游標懸停時能看到解釋。

**重要排版規定：請絕對不要使用 Markdown 標題語法（如 #, ##, ### 等）來標示段落或 Figure，請一律使用粗體（例如 **Figure 1**）即可，以避免介面字體過大。**
"""
    print("正在呼叫 Gemini API 進行逐圖邏輯分析...")
    return call_gemini_with_fallback(prompt, api_key)

def analyze_limitations_and_future(title, abstract, discussion_text, api_key):
    """
    使用 Gemini API 對文獻進行批判性思考（研究限制與未來方向）分析。
    """
    if not api_key:
        print("⚠️ 未提供 Gemini API Key，跳過 LLM 分析。")
        return None
        
    prompt = f"""
請扮演一位頂尖的生醫領域博士後研究員（但請勿在輸出中提及此設定）。我會提供論文的標題、摘要與討論段落/全文內容，請為我進行分析並完成以下內容：

論文標題：{title}
摘要：{abstract}

討論區段或全文段落：
{discussion_text}

1. 請列出本篇研究的整整 2 點「研究限制 (Limitations)」，並指明與實驗技術、模型（例如：動物模型限制、樣本數等）相關的局限。
2. 請針對生醫領域的研究所學生，提出整整 2 點「未來可切入的後續研究方向 (Future Directions)」，並指明未來可搭配使用的先進實驗技術或補充模型。

輸出請使用繁體中文（台灣學術常用語）以 Markdown 格式呈現，保持精簡、專業。請直接條列這四個要點，不要包含多餘的引入語或「Journal Club」等字眼。
若在輸出中包含生醫重要專有名詞或縮寫（如 VTA、DREADDs 等），請自動加上 HTML 懸停提示語法，例如：`<span title="此處填寫簡短的中文解釋" style="border-bottom: 1px dotted #888; cursor: help;">專有名詞</span>`，讓使用者游標懸停時能看到解釋。

**重要排版規定：請絕對不要使用 Markdown 標題語法（如 #, ##, ### 等）來標示段落，請一律使用粗體即可，以避免介面字體過大。**
"""
    print("正在呼叫 Gemini API 進行批判性思考分析...")
    return call_gemini_with_fallback(prompt, api_key)

def analyze_paper_qa(doc_data, question, api_key):
    """
    使用 Gemini API 進行單篇文獻問答 (RAG)。
    """
    if not api_key:
        print("⚠️ 未提供 Gemini API Key，跳過問答。")
        return None

    title = doc_data.get('title', '')
    abstract = doc_data.get('abstract', '')
    discussion = doc_data.get('discussion', '')
    figures = doc_data.get('figures', [])
    
    figs_text = ""
    for fig in figures:
        figs_text += f"- **{fig.get('label', 'Fig')}**: {fig.get('caption', '無說明')}\\n"

    prompt = f"""
你是一位專業的生醫研究助理。請根據以下提供的文獻內容回答使用者的問題。

文獻標題：{title}
摘要：{abstract}
討論與全文段落：{discussion}
圖表說明：\\n{figs_text}

使用者的問題：
{question}

請遵循以下規則：
1. 僅使用上述提供的文獻資訊來回答。
2. 回答請使用繁體中文（台灣學術常用語），並使用 Markdown 格式。
3. 若文獻中完全沒有提及或無法推導出答案，請誠實回答「本文未提及」，並務必在回應的最後獨立一行加上 `[NOT_MENTIONED]` 這個關鍵字。
"""
    print(f"正在呼叫 Gemini API 進行文獻問答: {question}")
    return call_gemini_with_fallback(prompt, api_key)

def analyze_single_term(term, api_key):
    """
    使用 Gemini API 對單一專有名詞進行深入解析。
    """
    if not api_key:
        return "⚠️ 未提供 API Key。"
        
    prompt = f"""
請扮演一位生醫領域的專家，為我詳細解釋以下專有名詞：
【 {term} 】

請提供：
1. 一句話精簡定義。
2. 該名詞在生醫領域（如神經科學、分子生物學等）的作用或重要性。
3. 如果適用，請舉一個相關的實驗技術或臨床疾病作為例子。

輸出請使用繁體中文，並以 Markdown 格式排版，不要超過 300 字。
"""
    return call_gemini_with_fallback(prompt, api_key)

# ==========================================
# 測試區塊 (執行此檔案時才會跑這裡的程式碼)
# ==========================================
if __name__ == "__main__":
    # 強制將 Windows 終端機輸出設定為 UTF-8，以支援 Emoji 顯示
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    print("=== 系統狀態檢查 ===")
    is_ntu = is_public_ip_ntu_range()
    if is_ntu:
        print("🟢 狀態: 已連線至台大網路 (140.112.*)，可存取完整學術資源！")
    else:
        print("🔴 狀態: 目前為外部網路，部分文獻可能僅能查看摘要。")
        
    print("\n=== 文獻抓取測試 ===")
    # ⚠️ 請一定要填入你的真實 Email
    MY_EMAIL = "iamiris515@gmail.com" 
    TEST_KEYWORD = "optogenetics cerebellum"
    
    # 測試抓取 3 篇文獻
    results = search_pubmed_titles_abstracts(query=TEST_KEYWORD, email=MY_EMAIL, max_results=3)
    
    for i, paper in enumerate(results, 1):
        print(f"\n[{i}] {paper['title']}")
        # 摘要太長的話，只印出前 150 個字預覽
        preview = paper['abstract'][:150] + "..." if len(paper['abstract']) > 150 else paper['abstract']
        print(f"摘要: {preview}")

    print("\n=== Semantic Scholar 上下游引文抓取測試 ===")
    # 我們拿一篇極具代表性的光遺傳學重大論文 DOI 來測試 (Boyden et al., 2005)
    TEST_DOI = "10.1038/nn1525" 
    
    s2_data = fetch_semantic_scholar_context(TEST_DOI)
    
    if s2_data:
        print(f"\n[核心論文] {s2_data['title']}")
        
        # 預覽上游文獻 (取前 2 篇)
        print("\n🔍 上游參考文獻 (References) 預覽:")
        for i, ref in enumerate(s2_data['references'][:2], 1):
            ref_title = ref.get('title') or '無標題'
            print(f"  {i}. {ref_title}")
            
        # 預覽下游文獻 (取前 2 篇)
        print("\n🔍 下游引用文獻 (Citations) 預覽:")
        for i, cit in enumerate(s2_data['citations'][:2], 1):
            cit_title = cit.get('title') or '無標題'
            print(f"  {i}. {cit_title}")

    print("\n=== Gemini API LLM 測試 ===")
    # ⚠️ 這裡請替換成你真實的 Google Gemini API Key
    # 取得免費 API Key 網址: https://aistudio.google.com/app/apikey
    # ⚠️ 安全機制：從 secrets 讀取金鑰，絕對不要在這裡寫死字串
    import streamlit as st
    try:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        GEMINI_API_KEY = ""
    
    if GEMINI_API_KEY:
        print("\n[測試 1] 動態客製化分群")
        focus = "實驗動物模型與技術"
        cluster_result = analyze_papers_clustering(results, focus, GEMINI_API_KEY)
        if cluster_result:
            print("\n💡 AI 分群結果:")
            print(cluster_result)
            
        print("\n[測試 2] 脈絡追蹤總結")
        if s2_data:
            context_result = analyze_citation_context(s2_data['title'], s2_data['references'], s2_data['citations'], GEMINI_API_KEY)
            if context_result:
                print("\n💡 AI 脈絡分析結果:")
                print(context_result)
    else:
        print("⚠️ 尚未填寫 GEMINI_API_KEY，請至程式碼第 155 行填寫後再測試 AI 功能。")