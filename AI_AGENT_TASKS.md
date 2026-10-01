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
    - **Contact Detail**: 可直接編輯 `custom_name`、`contact_type`、聯絡資訊、`notes`（內部資料，不得對外傳送）與標籤；LINE 原始資料唯讀；顯示相關案件。
    - **標籤 (Tags)**: 建立、改名、改色、刪除、指派／移除、批次指派／移除、依標籤篩選；業務角色（顧客、加盟商、供應商等）以標籤表示，不建立 Core Enum；標籤顏色不得作為唯一資訊。
    - **批次操作 (Bulk Actions)**: 僅加標籤、移除標籤、更新訂閱。
    - **工作區隔離**: Contact、Tag 皆依 `workspace_id` 隔離，跨工作區不得讀取、搜尋或修改。
    - **Phase 1 不實作**: Owner／Assignee、Queue、Sales Pipeline、Lead Score、關係圖、階層標籤、審核流程、CRM／行銷自動化（見規格「29. Phase 1 明確不實作」章節）。
- [x] **訂閱管理**: 按模組查看可訂閱項目；訂閱與標籤分離，Contact Detail 只顯示訂閱狀態，啟用／停用由訂閱模組處理。
- [x] **日誌與稽核 (Log & Audit)**: 提供必要的發送歷史與權限變更紀錄查閱；不建立獨立的 Enterprise Audit／Compliance Engine。

### 第四階段：新需求 - 案件管理 (New Requirement: Case Management)
*重點：從 LINE 對話中手動建立案件並追蹤進度。*
*規格依據：所有案件相關實作必須遵循 `docs/功能規格/案件管理流程規格.md`（狀態、等待分類、資料模型與「12. AI Agent Implementation Rules」章節），本節與規格衝突時以規格為準。*
- [ ] **建立案件 (Case Creation)**: 從對話選取訊息 $\rightarrow$ 「建立案件」按鈕 $\rightarrow$ 自動帶入工作區/OA 資訊；系統先解析該 LINE Identity 所屬的 `Contact`，並以 `Contact.id` 寫入 `case_subject_id`（Domain 概念稱 Case Subject，資料庫與 API 欄位固定為 `case_subject_id`，不存物件或 LINE `userId`；見聯絡人管理規格「20. Contact 與 Case Management」章節）。建立後狀態為 `pending`，並寫入 `create_case` Activity。
- [ ] **案件狀態流轉 (Case Status)**: 僅使用五個主狀態 `pending` / `processing` / `waiting` / `ready_to_close` / `closed`（UI 顯示：待處理／處理中／等待中／待結案／已結案），且只允許規格「8.1 允許的狀態轉換（Allowed Transitions）」列出的轉換；不得新增其他狀態（如「待對方回覆」、「等待財務」）。
- [ ] **等待狀態 (Waiting State)**: 進入 `waiting` 時必填 `waiting_party`（`internal` / `case_subject` / `third_party`）與 `waiting_reason`，`waiting_since` 由系統寫入。
- [ ] **處理紀錄 (Case Activity / Timeline)**: 處理記錄、溝通、內部確認等寫入 `CaseActivity`，每次狀態變更自動產生 `status_change` 紀錄；狀態與紀錄分離，結案後保留完整 Timeline。
- [ ] **待結案與結案**: `ready_to_close` 可退回 `processing` 或執行結案；結案時填寫 `resolution` 並寫入 `closed_at`。結案規則不寫死，由企業 SOP 決定。
- [ ] **優先級 (Priority)**: 依規格資料模型提供 `priority` 欄位設定。
- **Phase 1 不實作**: 承辦人指派 (Assignee / Handler)、重新開案 (Reopen，`closed` 為終態)。

## 📋 開發規範與規則 (Coding Standards & Rules)
1.  **禁止引入新框架**: 除非特別指示，否則堅持使用 Vanilla JS。目前不加入 React/Vue。
2.  **無障礙優先 (Accessibility First)**: 每個 UI 元件必須通過 AA 對比度檢查。
3.  **命名規範 (Naming Conventions)**: 使用具描述性的 Class 名稱；遵循現有專案的 API 調用模式。
4.  **手機版邏輯**: 確保「抽屜式元件 (Drawer)」在手機視窗下正常運作。
5.  **測試驗證**: 每個新功能必須配備對應的 Python 測試案例與手動瀏覽器隔離驗證。
6.  **Small Team First**: 本系統主要服務 1–3 位後台管理員，適用於所有模組（聯絡對象、案件、訊息、排程等）。不得自行加入主要用於大型團隊的 Owner、Assignee、Queue、Multi-level Approval、SLA Engine、Workflow Engine、Department Routing 等架構，除非規格明確要求。

## 📝 AI Agent 任務執行協定 (Task Execution Protocol)
1.  **分析需求**: 閱讀 `docs/需求與規劃/SaaS平台與全站Tailwind改版規劃.md` 中的特定章節；聯絡對象相關任務另須閱讀 `docs/功能規格/聯絡人管理規格.md`，案件管理相關任務另須閱讀 `docs/功能規格/案件管理流程規格.md`。
2.  **檢查現有代碼**: 確認現有的 API Endpoints 與 HTML 結構以確保相容性。
3.  **核對完成清單**: 確認任務是否已經在 [Done] 清單中，避免重複開發。
4.  **規劃修改**: 在執行前，先概述將要變動的檔案與內容。
5.  **逐步實作**: 以小範圍、可測試的增量進行程式碼修改。
6.  **驗證結果**: 對於每個元件完成後，執行測試或手動驗證。
