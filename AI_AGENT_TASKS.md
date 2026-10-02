# AI Agent 實作任務：SaaS 平台與全站 Tailwind 改版規劃

## 🎯 專案概述 (Project Overview)
將現有的 LINE 多 OA 管理平台轉換為現代化的 **Apple 風格 UI**，並使用 **Tailwind CSS** 進行重構。核心目標是確保「全站 Apple 風格」的一致性，並在保留既有功能基礎上，完成剩餘模組的開發與新需求的整合。

## ⚠️ 重要警告：禁止重複工程 (Anti-Redundancy Rule)
**AI Agent 在執行任務前，必須先核對 [已完成清單]。若該功能已被標記為完成，嚴禁重新撰寫邏輯、重構資料庫結構或重新設計 UI 框架。僅可在必要時進行樣式微調以符合 Apple 風格規範。**

## ✅ 已完成清單 (Completed - DO NOT RE-IMPLEMENT)
這些功能已實作並通過驗證，AI Agent 僅能對其進行視覺上的整合調整：
- [x] **全站亮色模式 (Light Mode Only)**: 深色模式已移除，全站統一為亮色。
- [x] **身份驗證系統**: 包含站內帳密登入、公開入口切換與使用者登入功能。
- [x] **組織權限架構**: 個人/組織多 OA 實作並完成資料庫升級已完成。
- [x] **LINE 連線基礎**: 多 OA 支援、憑證加密、專屬 Webhook、工作區切換與資料隔離。
- [x] **報告中心核心功能**: 搜尋、清單/卡片切換、詳情頁面、來源登記預覽及內建天氣恢復。

## 📚 功能規格文件 (Specifications)
以下規格為對應模組的最高依據，本任務清單與規格衝突時以規格為準：
- [聯絡人管理規格](docs/功能規格/聯絡人管理規格.md)：第三階段「聯絡對象管理」。
- [案件管理流程規格](docs/功能規格/案件管理流程規格.md)：第四階段「案件管理」。
- [聊天功能規格](docs/功能規格/聊天功能規格.md)：第五階段「聊天」。
- [權限與角色規格](docs/功能規格/權限與角色規格.md)：甲、乙、丙、丁四級權限，所有模組的權限以此為準。

## 🛠 技術棧與限制 (Technical Stack & Constraints)
- **前端**: Vanilla HTML, JavaScript, Tailwind CSS。
- **樣式設計**: 以 `styles/app.css` 為主要進入點；遵循 Apple iOS/macOS 設計語言（高留白、清楚層級）。
- **主色調**: 保留 `#00B900`（背景與輔助色使用低飽和度的綠色系）。
- **無障礙設計 (Accessibility)**: 必須符合 AA 對比度要求（最低 5.297:1）。
- **響應式設計 (Responsive Design)**: 以手機版優先規劃，窄螢幕採單欄顯示詳情。
- **後端與資料**: Python, SQLite, 沿用現有 API Endpoints（第一階段不進行資料遷移）。

## 🚀 待執行路線圖 (Pending Roadmap)

### 第一階段：全站 UI 一致性與整合 (UI Consistency & Integration)
*重點：將既有功能「完整接上」Apple 風格，確保視覺高度統一。*
- [x] **Tailwind 全域優化**: 在 `styles/app.css` 中完善 Apple 風格的 Utility Classes 與組件規範（如按鈕圓角、陰影、卡片層級、AA 對比）。
- [x] **共用元件標準化**: 統整側欄 (Sidebar)、工具列 (Toolbar) 與工作區標頭在所有頁面的視覺呈現。
- [x] **驗證流程 UI 優化**: 完成「登入 -> 工作區選擇 -> OA 選擇」流轉中的視覺過渡與互動細節。

### 第二階段：內容與訊息模組開發 (Content & Messaging Development)
- [x] **訊息中心 (Message Center)**:
    - 實作草稿、範本、立即/預約發送 UI（連接現有 API）。
    - 多格式訊息支援介面設計（文字、單圖/多圖、圖文卡片 Bubble、輪播卡片 Carousel、圖文訊息 Imagemap 與報告來源）。
- [x] **排程管理 (Scheduling Management)**:
    - 使用現有「單次預約 API」，建立獨立的「排程」頁面與執行紀錄視圖。

### 第三階段：對象與互動模組開發 (Object & Interaction Development)
*規格依據：聯絡對象相關實作必須遵循 `docs/功能規格/聯絡人管理規格.md`（Small Team First，1–3 位後台管理員；「30. AI Agent Implementation Rules」章節），本節與規格衝突時以規格為準。*
- [x] **聯絡對象管理 (Contact Management)**: 核心 Domain 固定為 `Contact`（聯絡對象），LINE User Identity 屬於 `ContactIdentity`；既有 LINE User／Recipient／Follower／Profile／Tag 資料表必須先 Mapping 沿用，不得重新建表或 Migration。`ContactIdentity` 為 Domain Concept；若既有 Schema 已有等價資料結構，Phase 1 不要求建立名為 `ContactIdentity` 的新資料表。
    - **顯示名稱**: 依序 `custom_name` → LINE `displayName`（群組為 `groupName`）→ fallback；LINE 相關名稱一律以 LINE API 原始回傳參數為準，對照見規格「7.1 LINE API 原始參數對照」章節；`custom_name` 只影響站內顯示，不回寫 LINE Profile，原始名稱保留可查。
    - **Contact List**: 搜尋（`custom_name`、LINE `displayName`、LINE `userId`、備註、標籤名稱）、標籤篩選、排序、多選；顯示主要名稱、原始 LINE `displayName`、標籤、訂閱狀態、最後互動時間。
    - **聯絡對象類型與聯絡資訊**: `contact_type` 分 `organization`（組織／團體，不限公司行號，含協會、班級、俱樂部、好友團等）、`person_business`（公務對象個人）、`person_private`（一般個人），未選為「未分類」；依類型顯示電話、Email、郵遞區號、地址，公務對象另有對方組織、職稱、公務電話、分機、公務 Email（見規格「6.1 聯絡對象類型」、「6.2 聯絡資訊欄位」）。
    - **UI 用語**: 名單與管理稱「聯絡對象」，發送時選擇的對象稱「發送對象」；不得使用「收件者」、「收件人」或「聯絡人」。後台沒有「一般收件者」角色，只在 LINE 收訊的人不建立帳號（見規格「3. 核心 Domain 定義」）。
    - **組織用語**: 「組織」單一定義（非個人團體），依層面分「系統組織／系統部門」（系統使用者層面，決定報表與發送範圍，現有欄位 `recipients.company`／`department`）與「對方組織」（對話對象層面，`organization_name`，只供辨識）；兩者互不同步、不建立關聯，畫面不得只寫「組織」。編輯畫面分「聯絡資訊」與「系統設定」兩區（見規格「6.3 組織用語」、「15.1 聯絡對象編輯畫面分區」）。
    - **Contact Detail**: 可直接編輯 `custom_name`、`contact_type`、聯絡資訊、`notes` 備註（內部資料，不得對外傳送）與標籤；LINE 原始資料唯讀；顯示相關案件。
    - **標籤 (Tags)**: 建立、改名、改色、刪除、指派／移除、批次指派／移除、依標籤篩選；業務角色（顧客、加盟商、供應商等）以標籤表示，不建立 Core Enum；標籤顏色不得作為唯一資訊。
    - **批次操作 (Bulk Actions)**: 僅加標籤、移除標籤、更新訂閱。
    - **工作區隔離**: Contact、Tag 皆依 `workspace_id` 隔離，跨工作區不得讀取、搜尋或修改。
    - **Phase 1 不實作**: Owner／Assignee、Queue、Sales Pipeline、Lead Score、關係圖、階層標籤、審核流程、CRM／行銷自動化（見規格「29. Phase 1 明確不實作」章節）。
- [x] **聯絡對象進階功能（2026-10-01 新增）**: 參考 LINE 聊天進階方案，上限依單台 PC 縮小；所有上限集中定義於後端一處，由後端檢查、前端顯示「目前數量／上限」。
    - **對話記事本**: 屬於 LINE 聊天室，與聯絡對象的備註 `notes` 是不同功能、互不同步。每個聊天室最多 100 筆；每筆有標題、類型、記事標籤（每 OA 最多 30 個、每筆最多 5 個）、內容 1–1,000 字、置頂（最多 5 筆）。修改須按「儲存」才生效，含未儲存提醒、同時編輯衝突檢查、最近刪除 30 天可還原（見聊天規格「9.1 對話記事本管理」）。與案件共用規則：關於成員、分類自訂與產業範本、防誤觸鎖定、期限、證據保存、轉為案件（見案件規格「17. 記事與案件共用規則」）。
    - **數量上限**: 每個 OA 最多 100 個標籤、每個聯絡對象最多 10 個標籤、單次批次操作最多 200 個聯絡對象；批次指派略過已達上限者並回報筆數（見規格「12.3 數量上限」）。
    - **修正批次操作**: `/api/contacts/bulk` 須檢查操作者為管理員，並驗證每個聯絡對象屬於目前 OA，不得寫入不存在的對象。
    - **自訂篩選條件**: 每個 OA 最多 10 個，同 OA 管理員共用；條件限規格「13.2 自訂篩選條件」所列，條件之間為「且」，即時計算並顯示筆數，可在「建立發送」帶入為發送對象；不提供巢狀條件或自動動作。
- [x] **訂閱管理**: 按模組查看可訂閱項目；訂閱與標籤分離，Contact Detail 只顯示訂閱狀態，啟用／停用由訂閱模組處理。
- [x] **日誌與稽核 (Log & Audit)**: 提供必要的發送歷史與權限變更紀錄查閱；不建立獨立的 Enterprise Audit／Compliance Engine。

### 第四階段：新需求 - 案件管理 (New Requirement: Case Management)
*重點：從 LINE 對話中手動建立案件並追蹤進度。*
*規格依據：所有案件相關實作必須遵循 `docs/功能規格/案件管理流程規格.md`（狀態、等待分類、資料模型與「12. AI Agent Implementation Rules」章節），本節與規格衝突時以規格為準。*
- [x] **建立案件 (Case Creation)**: 從對話選取訊息 $\rightarrow$ 「建立案件」按鈕 $\rightarrow$ 自動帶入工作區/OA 資訊；系統先解析該 LINE Identity 所屬的 `Contact`，並以 `Contact.id` 寫入 `case_subject_id`（Domain 概念稱 Case Subject，資料庫與 API 欄位固定為 `case_subject_id`，不存物件或 LINE `userId`；見聯絡人管理規格「20. Contact 與 Case Management」章節）。建立後狀態為 `pending`，並寫入 `create_case` Activity。
- [x] **案件狀態流轉 (Case Status)**: 僅使用五個主狀態 `pending` / `processing` / `waiting` / `ready_to_close` / `closed`（UI 顯示：待處理／處理中／等待中／待結案／已結案），且只允許規格「8.1 允許的狀態轉換（Allowed Transitions）」列出的轉換；不得新增其他狀態（如「待對方回覆」、「等待財務」）。
- [x] **等待狀態 (Waiting State)**: 進入 `waiting` 時必填 `waiting_party`（`internal` / `case_subject` / `third_party`）與 `waiting_reason`，`waiting_since` 由系統寫入。
- [x] **處理紀錄 (Case Activity / Timeline)**: 處理記錄、溝通、內部確認等寫入 `CaseActivity`，每次狀態變更自動產生 `status_change` 紀錄；狀態與紀錄分離，結案後保留完整 Timeline。
- [x] **待結案與結案**: `ready_to_close` 可退回 `processing` 或執行結案；結案時填寫 `resolution` 並寫入 `closed_at`。結案規則不寫死，由企業 SOP 決定。
- [x] **優先級 (Priority)**: 依規格資料模型提供 `priority` 欄位設定。
- [x] **案件編號 (Case Number)**: 格式 `{前綴}-{YYYYMM}-{4 位流水號}`（例 `216RUX-202610-0042`），流水號每月重新起算。前綴預設取 OA LINE ID（`line_channels.basic_id`）去掉 `@` 後前 6 碼轉大寫，可修改；全平台唯一，重複時警告並拒絕儲存。修改前綴時選擇「只套用新案件」或「覆蓋既有編號」，覆蓋時舊編號保留為別名可搜尋。建立交易內取號、`case_no` 唯一限制、不可單筆修改不回收（見規格「14. 案件編號」）。
- [x] **案件歷程與跨年度查詢**: 聯絡對象與聊天面板顯示歷年案件；案件與處理紀錄永久保存，從對話建立時保存訊息快照；同一問題以「延續案件」關聯前案而非重新開啟；選填參考編號（訂單號、產品序號等），可跨年度搜尋（見規格「15. 案件歷程與跨年度查詢」）。
- [x] **匯出 CSV／XLSX**: 匯出目前篩選結果（單次最多 5,000 件），可選含處理紀錄與聯絡資訊；CSV 為 UTF-8 含 BOM、防公式注入；XLSX 以標準函式庫產生不新增套件；僅管理員可匯出並寫入操作紀錄（見規格「16. 匯出」）。
- [x] **記事與案件共用規則**: 案件對象可為群組中的個別成員；案件類別由各 OA 自訂（最多 20 項，「一般」保留）並可套用產業範本；🔒 防誤觸鎖定（不設權限模組）；選填期限與逾期標示；被引用的訊息與媒體永久保存；記事可轉為案件、聯絡對象詳情彙整記事與案件、案件可通知對象進度（見規格「17. 記事與案件共用規則」）。
- [x] **範本包（案件範本、記事範本、分類組合）**: 兩層結構「範本包 → 分類組合／案件範本／記事範本」；內建 8 個唯讀預設範本包（通用＋7 種產業），每個 OA 勾選啟用（預設只啟用通用），選範本時依範本包分組。自訂範本包屬於工作區（最多 20 個，每包案件範本與記事範本各最多 20 個），可新增、複製、由現有案件／記事存成範本、搬移、鎖定、刪除；範本帶入後按「儲存」才建立。分類組合套用分「取代／合併」並先預覽。集中於「範本與分類」頁（見規格「17.1–17.6」）。
- **Phase 1 不實作**: 承辦人指派 (Assignee / Handler)、重新開案 (Reopen，`closed` 為終態)。

### 第五階段：新需求 - 聊天 (New Requirement: Chat)
*重點：參考 LINE Official Account Manager 的聊天、聯絡人、篩選傳訊與聊天設定，在本平台查看與回覆 LINE 對話。*
*規格依據：`docs/功能規格/聊天功能規格.md`；與規格衝突時以規格為準。單台 PC，所有上限集中定義於後端一處。*
- [x] **階段 A 唯讀檢視**: 三欄聊天畫面（列表、對話、右側面板）、群組成員名稱快取、右側面板（聯絡對象、標籤、對話記事本、相關案件）、聯絡對象頁補「聊天」與最近聊天日期、標籤管理頁。
- [x] **階段 B 回覆與日常管理**: 文字回覆（`replyToken` 有效時用 reply，否則 push 並提示額度）、outbound 寫入對話紀錄、未讀／待處理／處理完畢、預設訊息（每 OA 100 則）、預約訊息清單（同時最多 50 則）、自訂篩選條件、篩選傳訊（併入「建立發送」）、瀏覽器提醒、輪詢更新。
    - 2026-10-01 清點：其餘已實作；**篩選傳訊**（「建立發送」依標籤／依自訂篩選條件選發送對象）與**瀏覽器通知**（聊天設定的通知勾選框存在，但未呼叫瀏覽器 Notification）尚未實作。
    - 2026-10-02 完成：篩選傳訊、瀏覽器通知與聊天輪詢（每 10 秒，多分頁只由一頁輪詢與通知）；預約訊息同時 50 則上限改由後端檢查。
- [x] **階段 C 搜尋、媒體、匯出與回應時間**: 對話內搜尋、媒體下載保存（1 年、單檔 20 MB、總量 10 GB）、匯出聊天紀錄、回應時間（只控制通知）。
- **不實作**: 負責人員、AI 聊天機器人、自動回覆、LINE 通話、對方已讀狀態、與 LINE 官方後台同步。

### 第六階段：權限與管理介面 (Roles & Admin UI)
*規格依據：`docs/功能規格/權限與角色規格.md`（甲、乙、丙、丁四級；第 6 節決定事項；第 8 節管理介面）。所有模組的權限以此為準。*
*2026-10-01 查核：工作區已有部分初版程式（尚未提交），以下「現況」為查核結果；每項須完成「驗收」才可勾選。*

**狀態**：2026-10-01 依使用者確認標為完成（僅抽查甲級唯讀、供應商查看紀錄、OA 一覽、我的帳號）；「取消個人工作區」移至第七階段，於資料庫重建時以新結構直接處理。

- [x] **丁級協作人員 (`assistant`)**：新增角色、資料庫 CHECK 升級（建新表→複製→換名，先備份）、可閱讀對話與操作記事／案件／聊天狀態／聯絡對象，不能傳送任何 LINE 訊息（規格 2、3、4）。
    - 現況：schema、`app.py` 升級與 `reports.py` 已有初版；前端未見。
    - 驗收：舊資料庫升級後資料完整且可重複執行；丁級呼叫每個傳送 API（聊天回覆、推播、預約、篩選傳訊、案件通知對象、報告發送）皆 403；丁級導覽只顯示工作總覽、聊天、聯絡對象、案件。
- [x] **甲級對客戶內容唯讀**：甲級（含本機管理員）對客戶 OA 的聊天、記事、案件、聯絡對象、標籤、聊天狀態、範本與分類只能閱讀；可做平台建置與 OA 技術設定；不能匯出客戶資料（規格 3、6.4）。
    - 現況：只擋了 `/api/chat/send`、`/api/send`；其餘寫入未擋，且註解與實作不符。
    - 驗收：以甲級身分對規格第 3.2 節每一項寫入 API 測試皆 403；閱讀 API 皆 200；OA 技術設定與組織建立仍可用。
- [x] **甲級閱讀紀錄**：甲級閱讀某組織的聊天、記事或案件時寫入操作紀錄，乙級可在本組織操作紀錄看到「供應商曾於某時間查看」（規格 6.2）。
    - 現況：未實作。
    - 驗收：甲級閱讀後該組織操作紀錄出現一筆；乙級看得到、丙丁級看不到；其他組織看不到。
- [x] **乙級管理本組織人員**：乙級可新增、停用丙、丁級帳號、產生登入設定連結、勾選可用 OA、設定客製模組授權；不能建立甲、乙級或存取其他組織（規格 3.1、6.1、8.4）。
    - 現況：`reports.py` 已有部分限制邏輯。
    - 驗收：乙級建立丙、丁級成功；建立甲、乙級與操作其他組織人員皆拒絕；丙、丁級只能使用被勾選的 OA。
- [x] **丙級操作人員**：對話與發送與乙級同級，所屬 OA 全部對話可讀可回；「發送範圍授權」只用於客製模組（例如天氣訂閱）；畫面名稱改為「操作人員」，程式角色值 `sender` 不變（規格 2、3）。 2026-10-02 完成。
- [x] **視角預覽檢視／編輯切換**：甲級只能檢視；乙級預覽本組織丙、丁級，點 🔒 切換編輯後依被預覽者等級操作；紀錄記為預覽者本人並註明視角；每次進入回到檢視（規格 5）。
    - 現況：`admin_server.py` 已有 `preview_edit` 初版。
    - 驗收：甲級預覽時所有寫入 403；乙級未切換編輯時寫入 403、切換後可寫入；預覽丁級時傳送 403；操作紀錄記錄預覽者與被預覽者。
- [x] **OA 一覽與 OA 切換器**：可用 2 個以上 OA 時登入後進入 OA 一覽（OA 名稱、組織、好友、我的等級、未讀、待處理；跨組織、可搜尋排序；不顯示方案與額度），1 個 OA 直接進入；頂端 OA 切換器取代「先選組織再選 OA」（規格 8.1、8.2）。
    - 現況：未實作。
    - 驗收：多 OA、單 OA、甲級三種帳號的登入落點正確；切換器可搜尋、依組織分組、顯示未讀；好友數由背景快取更新。
- [x] **依等級的管理選單與我的帳號**：甲級「組織／LINE OA／平台設定」，乙級「LINE OA／人員與權限／組織設定」，丙丁級無；拆分現有「帳號與設定」；右上角「我的帳號」（規格 8.3、8.4）。
    - 現況：未實作（仍為「LINE OA 管理／組織管理／帳號與設定」）。
    - 驗收：四級各自看到的選單與規格一致；直接呼叫未顯示選單的 API 也被拒絕。
- [x] **乙級首次登入引導**：工作總覽顯示開通清單（確認 OA 連線、選擇範本包、新增同事），完成自動打勾、可略過（規格 8.6）。
    - 驗收：完成或略過後不再顯示。
- [x] **權限測試總表**：以規格第 3 節權限表為準，建立自動化測試逐格驗證甲、乙、丙、丁四級對各 API 的允許／拒絕；後端檢查不得只靠前端隱藏。

### 第六階段補完：2026-10-01 清點結果 (Audit Follow-up)
*2026-10-01 逐項對照程式碼、API 端點與 133 個 Python 測試的結果；畫面只實測甲級管理選單。建議在第七階段前或與第七階段一起完成。*

**優先**
- [x] **丙級操作人員權限**：見第六階段同名項目。丙級與乙級對話、發送同級，不需授權即可讀取所屬 OA 聯絡對象、回覆與推播；發送範圍授權只用於客製模組。 2026-10-02 完成。
- [x] **篩選傳訊**：見第五階段「階段 B」。「建立發送」選擇發送對象時新增「依標籤（符合任一／全部）」與「依自訂篩選條件」，顯示人數並提示計入額度；聯絡對象與聊天列表提供「對這些對象發送」捷徑（聊天規格第 11 節）。 2026-10-02 完成。

**次要**
- [x] **自訂範本包與範本管理**：目前只有範本包清單、啟用切換、分類組合預覽與套用。待補：自訂範本包新增、編輯、複製、刪除、鎖定（每工作區最多 20 個）；自訂案件範本與記事範本新增、編輯、複製、搬移、刪除（每包各最多 20 個）；由現有案件或記事「存成範本」（案件規格 17.2–17.4）。 2026-10-02 完成。
- [x] **記事類型與案件類別單項管理**：目前只能整組套用；待補單項新增、改名、刪除、排序，刪除時改為「一般」，「一般」不可刪除（案件規格第 17 節第 2 條）。 2026-10-02 完成。
- [x] **記事標籤清單**：記事已以 `tags_json` 存標籤，每筆 5 個上限僅後端檢查；待補每個 OA 的記事標籤清單管理（最多 30 個）與依標籤篩選（聊天規格 9.1）。 2026-10-02 完成。
- [x] **記事同時編輯衝突檢查**：開始編輯時記版本，儲存時若已被他人修改則不覆蓋，提示並讓使用者選擇（聊天規格 9.1）。目前無版本欄位與檢查。 2026-10-02 完成。
- [x] **期限與已完成的畫面**：`due_date`、`is_completed` 欄位已存在；待補記事「標為已完成」、記事與案件「逾期」標示與篩選（案件規格第 17 節第 4 條）。 2026-10-02 完成。
- [x] **案件「通知對象」**：以範本產生進度訊息傳給案件對象，送出前依 7.1 提示額度、送出後寫入處理紀錄；丁級與甲級不可用（案件規格第 17 節第 6 條）。目前無 API 與按鈕。 2026-10-02 完成。
- [x] **瀏覽器通知**：見第五階段「階段 B」。依聊天設定的通知、音效、預覽偏好，以 Notification API 提示新訊息；非回應時間不通知；多分頁只由一頁通知（聊天規格 12.1、12.4）。 2026-10-02 完成。
    - 2026-10-02 複查補完：原 `notifyNewMessage()` 未被呼叫、聊天頁無輪詢、提醒勾選框未儲存。已補 `chat.js` 輪詢（localStorage 心跳選出單一負責分頁）、新進訊息通知、回應時間判斷（每週時段與例假日編輯，後端驗證格式），並修正 `chatAction` 中 `convert-note-to-case` 未關閉的區塊（原本導致對話內搜尋、匯出、聊天設定、清理媒體按鈕無作用）。

**之後**
- [x] **聊天頁左側選單維持標準寬度**：依使用者指示，進入聊天頁時左側導覽維持全站統一標準寬度（不自動收合為圖示窄欄）；右側面板支援展開/收合。 2026-10-02 完成。
- [x] **上限集中定義**：目前分散在 `chat_notes.py`（`LIMITS`）、`recipients.py`（標籤 100／10／200 寫死）、`chat.py`（媒體）等；集中到單一模組並由各處引用。 2026-10-02 完成。
    - 2026-10-02 複查補完：原程式未集中。已新增 `limits.py` 為唯一定義處，`chat.py`、`chat_notes.py`、`recipients.py`、`template_packs.py`、`cases.py`、`admin_server.py` 改為引用；`/api/session` 回傳 `limits` 供前端顯示；補上原本未檢查的「記事標籤每 OA 30 個」與「預約訊息同時 50 則」。測試 `tests/test_limits.py`。
- [x] **權限測試總表**：目前 `test_roles_and_permissions.py` 7 個測試；依權限規格第 3 節逐格補齊四級對各 API 的允許與拒絕。 2026-10-02 完成。
- [x] **客製模組授權的歸屬**：規格為乙級授權給本組織丙級，程式 `/api/dispatch-scopes/save`、`/api/sender-grants/save` 仍限甲級；與「丙級操作人員權限」一起調整，並讓「組織 › 人員與權限、發送範圍」分頁移到乙級的「人員與權限」。 2026-10-02 完成。


### 第七階段：資料庫重建 (Clean Schema Rebuild)
*目的：刪除現有資料庫，依目前所有規格重寫一份乾淨的 `schema.sql` 直接建表，移除累積的升級語法、舊欄位與用不到的資料表。*
*2026-10-01 現況：`schema.sql` 39 張表；`app.py` 的 `initialize_database()` 有 17 行補欄位／重建表／清舊資料的升級程式；另有 `upgrade_multi_oa.py`。正式資料庫資料量很少（訊息 9 筆、聯絡對象 7 筆、OA 1 個、帳號 1 個、組織 2 個）。*

**原則：視為全新安裝、整個重來。** 不保留任何舊版相容路徑、升級程式或舊設定方式；所有程式、測試與文件都以「從零安裝的正式產品」為準。

**建議時機**：與第六階段一起或在其之前進行。乾淨重建後，第六階段的「個人工作區移轉」與「`assistant` CHECK 升級」都不必再寫升級程式，直接以新結構建立即可。

- [x] **盤點**：逐一列出 39 張表與每個欄位，以 `grep` 確認程式是否仍使用；整理成「保留／改名／刪除」清單，先提交使用者確認再動手。 2026-10-02 完成盤點與精簡化架構提案（39 表 ➔ 約 18 核心表）。
    - 已取消功能的殘留：個人工作區（`line_channels.owner_email`、`p:` 工作區）、`employee` 相關、舊帳號綁定（`workspace_users.recipient_id`、`report_sources.owner_email` 的舊相容讀取）、`line_channels.legacy_webhook`。
    - 命名與規格不一致：`recipients.company`（實為系統組織 ID，規格名 `organization_id`）、`recipients.alias`（規格名 `custom_name`）等；改名時程式、測試、前端一併修改。
    - 重複或用不到的表與索引。
- [x] **新 `schema.sql`**：依聯絡人、案件、聊天、權限規格重寫，作為唯一的資料結構來源。 2026-10-02 完成：保留 39 張表（未合併資料表；盤點時提到的「約 18 核心表」提案不在專案中），刪除個人工作區、`legacy_webhook`、`owner_email`、帳號 LINE 綁定（`workspace_users`／`organization_members` 的 `recipient_id`）等欄位；營運資料表的 `channel_id` 改為 NOT NULL 無預設值；補上角色、狀態、類型、旗標的 CHECK 與 `contact_tags(channel_id,name)` 唯一限制；`recipients.alias` 改名 `custom_name`。
    - 一致的命名、外鍵、CHECK、唯一限制與必要索引；所有營運資料帶 OA（`channel_id`）範圍。
    - 角色只有 `platform_admin`、`org_admin`、`operator`、`collaborator`；不建立個人工作區相關欄位。
    - 設定 `PRAGMA user_version = 1` 作為結構版本；之後若需變更，以編號的升級檔處理，不再把升級語法寫進 `initialize_database()`。
- [x] **產品設定改由網頁後台**：比照正式產品，LINE OA 與模組設定一律由甲級在網頁後台設定，不寫在 `.env`。 2026-10-02 完成：`control_runtime.load_settings()` 只讀三項部署設定；Webhook 只接受 `/webhook/<OA>` 並以該 OA 的 secret 驗證；天氣模組改為組織設定（`organizations.weather_image_path`，平台管理員在「組織」頁填寫）；刪除「匯入既有 OA」、單一 OA 模式、`upgrade_multi_oa.py`、`Send-WeatherReport.ps1` 與 `send_image.py` 命令列（確認無排程或其他專案使用；保留供發送服務使用的函式）；控制台移除「編輯 LINE 設定」，改顯示 Python 環境、`PUBLIC_BASE_URL` 與是否已有啟用中的 OA；`PUBLIC_BASE_URL` 未設定時發送會明確報錯（不再預設網域）。README、`line-oa-archive/README.md`、`LINE_OA申請與設定.md` 已改寫。**待使用者**：`.env` 清理（見「資料處理」）。
    - **移出 `.env`、改由網頁設定**：`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`（甲級在「LINE OA」頁輸入，加密存入資料庫）；`WEATHER_MODULE_ENABLED`、`WEATHER_OWNER_EMAIL`、`WEATHER_IMAGE_PATH`（甲級在「組織」頁為指定組織啟用與設定客製模組）；`ADMIN_ALLOWED_EMAILS`（改為首次設定，見下一項）；`LINE_PUSH_USER_ID`（隨 `send_image.py` 處理）。
    - **保留在 `.env`（部署基礎設定，網站啟動前就需要）**：只有 `DATABASE_PATH`、`PUBLIC_BASE_URL`、`ADMIN_PUBLIC_HOST`。
    - **移除舊路徑（全部刪除，不保留相容）**：「匯入既有 OA」（讀取 `.env` 憑證）、舊單一 OA 模式與 `legacy_webhook`、個人工作區、`employee` 清理、舊帳號綁定與 `owner_email` 相容讀取、`upgrade_multi_oa.py`，以及程式中所有讀取已移出變數的地方。
    - **桌面控制台**：移除「編輯 LINE 設定」（開啟 `.env` 記事本）按鈕；「設定：已填入必要設定」改為檢查部署設定與資料庫中是否已有啟用的 OA；未設定 OA 時提示「請以管理後台的 LINE OA 頁設定」。
    - **`send_image.py` 命令列工具**：改為讀取資料庫中的 OA 與聯絡對象，或在確認無人使用後移除。
    - **`.env.example`**：已於 2026-10-01 先改為新版（只列三項部署設定）；現有 `.env` 待程式完成後再清理。
    - **README、安裝說明**：同步改寫，只列保留的部署設定。
- [x] **第一位甲級帳號的首次設定**：不使用 `.env` 建立帳號（見權限規格「9. 首次設定」）。 2026-10-02 完成：`POST /api/setup/first-admin`（僅本機控制台 token、且尚無啟用中的平台管理員）、`/api/session` 的 `needs_setup`、登入頁 `/api/auth/setup-state`、`create_admin.py`；測試 `tests/test_first_run.py`。
    - **網頁首次設定**：資料庫沒有任何甲級帳號時，經桌面控制台開啟的本機入口直接進入「建立第一位平台管理員」：輸入 Email、顯示名稱，產生一次性設定密碼連結；建立後此頁不再出現。外部網址只顯示「系統尚未完成初始設定」。
    - **無桌面主機**：提供一次性指令 `create_admin.py`，互動輸入 Email 後印出一次性設定連結；不接受命令列密碼參數、不寫入任何檔案；已有甲級帳號時可用於新增甲級或重設密碼（緊急復原）。
    - 驗收：全新資料庫經本機入口可完成首次設定，外部網址無法進入設定頁；已有甲級後設定頁不再出現；`create_admin.py` 在無桌面環境可完成相同流程；任何檔案與日誌中都沒有明文密碼。
- [x] **移除 Cloudflare Access 登入**：網站只保留站內帳號密碼登入，不再支援 Cloudflare Access 模式與模式切換。 2026-10-02 完成：已刪除 `remote_auth.py`、`configure_login.py`、`tests/test_remote_auth.py`；`admin_server.py`／`site_auth.py` 以 `ADMIN_PUBLIC_HOST` 判斷對外網址並一律走站內登入；`/api/auth/config` 與登入頁 Access 提示移除；`requirements.txt` 改列 `cryptography`；測試改以 `tests/login_helper.py` 建立站內 Session。134 個 Python 測試通過；瀏覽器測試未執行。**待使用者**：Cloudflare 後台刪除 `line-admin` Access 應用程式；`.env` 的 `ADMIN_AUTH_MODE`、`CF_ACCESS_*`、`ADMIN_ALLOWED_EMAILS` 已不讀取，可刪除。
    - 刪除 `remote_auth.py` 與 `tests/test_remote_auth.py`、`configure_login.py`（登入模式切換工具）；移除 `ADMIN_AUTH_MODE`、`CF_ACCESS_TEAM_DOMAIN`、`CF_ACCESS_AUD`。
    - `site_auth.py`、`admin_server.py`、`control_runtime.py` 移除 Access 模式分支與 `Cf-Access-Jwt-Assertion` 處理；`requirements.txt` 移除 `PyJWT[crypto]`。
    - 調整相關測試（`test_site_auth.py`、`test_workspace.py`、`test_roles_and_permissions.py`、`test_control_runtime.py`、`tests/control_lifecycle.ps1`、`tests/workspace_fixture.py`），只測站內登入。
    - 文件：`docs/功能規格/網站登入.md` 改寫為只描述站內登入（或改名為「網站登入」），刪除切換與回復 Access 的步驟；README、`line-oa-archive/README.md`、專案需求、SaaS 規劃、進度紀錄同步更新。
    - **保留 Cloudflare Tunnel**：Tunnel 是對外連線通道，與 Access 登入無關，不刪除。程式完成後，由使用者在 Cloudflare 後台刪除 `line-admin` 的 Access 應用程式（目前為 Bypass）。
- [x] **管理選單依等級隱藏（修正）**：`index.html` 管理選單已有 `data-nav-role`，但 `admin.js` 未依此隱藏，所有人看到全部 5 項。依權限規格 8.3：甲級只顯示「組織、LINE OA」；乙級只顯示「LINE OA、人員與權限、組織設定」；丙、丁級不顯示管理選單。移除「平台設定」頁（甲級帳號改由本機管理員或 `create_admin.py` 處理，預設範本包內建於程式）。後端對應 API 也須依等級拒絕。驗收：四級各自登入，選單與規格一致；直接呼叫未顯示選單的 API 被拒絕。 2026-10-01 完成：甲級以 headless Chrome 實測只顯示「組織、LINE OA」；後端新增測試 `test_platform_admin_manages_only_org_admins_and_not_personnel`；瀏覽器測試已改寫但未執行（本機無 Playwright）。暫留「組織 › 平台管理員帳號」區塊供甲級設定登入，待第 9 節首次設定與 `create_admin.py` 完成後再評估。
- [x] **等級名稱與程式角色值**（規格「2. 等級總覽」「7. 實作注意」）： 2026-10-02 完成：角色值、`organization_id` 欄位與 API 欄位、`same_organization()`／`enforce_organization()`／`channels.current_organization_id()` 改名；畫面名稱與一行權限說明更新；管理選單鍵改為 `platform`／`org`／`platform-org`。
    - 畫面一律顯示「平台管理員、管理員、操作人員、協作人員」並附一行權限說明，不顯示甲乙丙丁或 ABCD。
    - 程式角色值改名：`administrator`→`platform_admin`、`company_admin`→`org_admin`、`sender`→`operator`、`assistant`→`collaborator`；新 `schema.sql` 的 CHECK 直接使用新值。
    - 欄位與函式改名：存放組織 ID 的 `company` 欄位改為 `organization_id`；`same_company()`、`enforce_company()` 等一併改名。
    - 範圍：Python、前端 JS、測試、fixture、規格與 README 同步修改。
    - 驗收：`grep` 確認程式與測試中已無舊角色值（`company_admin`、`assistant`，以及作為角色的 `administrator`、`sender`）與 `company` 欄位名；全部測試在新資料庫通過。
- [x] **取消個人工作區**：不再提供個人工作區；現有個人 OA 移轉到組織類型「個人」的組織，原擁有者設為乙級（規格 6.3）。重建資料庫時新結構直接不建個人工作區，不需另寫移轉程式。 2026-10-02 完成：程式與介面已無個人工作區；不寫移轉程式，資料於重建時重新設定（見「資料處理」）。
    - 現況：個人工作區程式（`personal_owner`、`owner_email`、`p:` 工作區）仍在。
    - 驗收：移轉前備份；移轉後原 OA 的聯絡對象、報告、發送紀錄、案件、記事完整；原擁有者以乙級登入可操作；介面不再出現個人工作區。
- [x] **移除升級程式**： 2026-10-02 完成：`initialize_database()` 只執行 `schema.sql` 並寫入 `PRAGMA user_version = 1`；偵測到沒有結構版本的舊資料庫時拒絕啟動並提示備份重建。`initialize_database()` 只執行 `schema.sql`，刪除所有 `ALTER TABLE`、重建表、清理舊資料的程式；刪除 `upgrade_multi_oa.py` 及其測試，並更新提到它的文件（`line-oa-archive/README.md`、SaaS 規劃、進度紀錄）。
- [x] **資料處理**：不移轉舊資料，直接重建。 2026-10-02 完成：停止服務後以 SQLite backup API 備份至 `line-oa-archive/backups/phase7-20261002_122714/`（含原始 `.db` 與 `line-credentials.key`，完整性檢查 ok）。備份時正式資料庫已是新結構（`user_version=1`）且全部資料表為空——12:23 控制台「重新啟動」前舊資料庫已不存在，舊資料（訊息 9 筆等）未在備份中。保留此空白新資料庫並重新啟動，本機與公開健康檢查正常，`/api/auth/setup-state` 回報尚未完成首次設定。**待使用者**：依權限規格 8.6 首次設定（平台管理員 → 自己的組織與管理員 → LINE OA 憑證）、LINE Developers 改用新 Webhook URL、清理 `.env`。
    - 執行前停止 LINE 服務，將 `data/line_archive.db`（含 `-wal`、`-shm`）備份到 `backups/`；保留 `line-credentials.key`。
    - 會遺失並需重新設定的項目：後台帳號與密碼、組織、OA 連線（由甲級在網頁「LINE OA」頁重新輸入 Channel access token 與 secret）、聯絡對象的自訂名稱與分類（之後對方傳訊息會重新建立聯絡對象）、9 筆訊息紀錄。
    - 重建後依權限規格 8.6 重新設定：甲級帳號、自己的組織（類型「個人」）與乙級帳號、OA 連線。
- [ ] **驗收**： 2026-10-02：131 個 Python 測試在全新資料庫通過（含 `tests/test_fresh_install.py`：只有三項部署設定，從首次設定、建立組織、網頁設定 OA、Webhook 收訊到發送；重複執行 `initialize_database()` 不改變結構）；`grep` 檢查通過；控制台 `tests/control_lifecycle.ps1` 通過。**未完成**：瀏覽器測試（本機無 Playwright，fixture 已改寫）、正式資料庫重建後實際走過一次。
    - 在全新資料庫上，全部 Python 測試與瀏覽器測試通過；測試 fixture 只依新 `schema.sql` 建立。
    - `grep` 確認程式中已無 `ALTER TABLE`、`RENAME TO`、`employee`、個人工作區、`import_existing`、`legacy_webhook`、`CF_ACCESS`、`ADMIN_AUTH_MODE`、`remote_auth`、`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN` 與已刪除欄位的引用。
    - 以只含 `DATABASE_PATH`、`PUBLIC_BASE_URL`、`ADMIN_PUBLIC_HOST` 的 `.env` 從零安裝，可完成：首次設定建立甲級帳號 → 建立組織 → 網頁設定 OA → Webhook 收訊 → 發送。
    - 重複啟動服務不會改動資料庫（`initialize_database()` 可重複執行）。
    - Webhook 收訊、聯絡對象建立、發送、案件、記事在新資料庫上實際走過一次。

## 📋 開發規範與規則 (Coding Standards & Rules)
1.  **禁止引入新框架**: 除非特別指示，否則堅持使用 Vanilla JS。目前不加入 React/Vue。
2.  **無障礙優先 (Accessibility First)**: 每個 UI 元件必須通過 AA 對比度檢查。
3.  **命名規範 (Naming Conventions)**: 使用具描述性的 Class 名稱；遵循現有專案的 API 調用模式。
4.  **手機版邏輯**: 確保「抽屜式元件 (Drawer)」在手機視窗下正常運作。
5.  **測試驗證**: 每個新功能必須配備對應的 Python 測試案例與手動瀏覽器隔離驗證。
6.  **Small Team First**: 本系統主要服務 1–3 位後台管理員，適用於所有模組（聯絡對象、案件、訊息、排程等）。不得自行加入主要用於大型團隊的 Owner、Assignee、Queue、Multi-level Approval、SLA Engine、Workflow Engine、Department Routing 等架構，除非規格明確要求。

## 📝 AI Agent 任務執行協定 (Task Execution Protocol)
1.  **分析需求**: 閱讀 `docs/需求與規劃/SaaS平台與全站Tailwind改版規劃.md` 中的特定章節；聯絡對象相關任務另須閱讀 `docs/功能規格/聯絡人管理規格.md`，案件管理相關任務另須閱讀 `docs/功能規格/案件管理流程規格.md`，聊天相關任務另須閱讀 `docs/功能規格/聊天功能規格.md`。
2.  **檢查現有代碼**: 確認現有的 API Endpoints 與 HTML 結構以確保相容性。
3.  **核對完成清單**: 確認任務是否已經在 [Done] 清單中，避免重複開發。
4.  **規劃修改**: 在執行前，先概述將要變動的檔案與內容。
5.  **逐步實作**: 以小範圍、可測試的增量進行程式碼修改。
6.  **驗證結果**: 對於每個元件完成後，執行測試或手動驗證。
