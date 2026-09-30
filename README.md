# LINE 自動化

## 網站帳號密碼登入

站內登入功能已完成，保留 Cloudflare Tunnel。既有帳號可從右上角「登入設定」建立密碼；平台管理員也能在「帳號與設定」提供 30 分鐘一次性啟用／重設連結、撤銷登入。支援保持登入、修改密碼與登出，沿用原有組織及發送範圍權限。

正式入口需先有管理員密碼，再執行 `line-oa-archive/configure_login.py --mode password`、重啟服務，最後調整 Cloudflare Access 的 `line-admin` 應用程式原則。完成前仍會看到舊 Access 驗證。完整操作、恢復方式及測試見 [網站登入與切換](網站登入與切換.md)。密碼與 Token 不填入 `.env` 或 Git。

## 全站工作台（Apple 風格＋Tailwind）

工作總覽、報告中心、訊息編輯／確認、收件者、訂閱、排程、發送紀錄、組織與帳號設定共用本機編譯的 Tailwind 主題。保留 `#00B900`、低飽和背景、系統／深／淺色及手機版。

- 報告中心可搜尋、切換清單／卡片，開啟詳情後預覽、設定來源、移除或建立發送。
- 點收件者名稱可查看組織、分類、訂閱及最近互動；有管理權限者可繼續編輯。桌面使用分欄，窄螢幕進入詳情後關閉即可返回清單。
- 工具列搜尋或 `Ctrl / ⌘ K` 可尋找目前已載入且有權限的頁面、報告與收件者；支援方向鍵、Enter 與 Escape。
- 「排程管理」查看單次預約、取消預約及執行異常；建立發送時於確認頁選擇「指定日期與時間」。顯示所有待發預約與最近載入的歷史，不代表完整歷史統計。

此階段完整接回現有 API 與權限；站內登入已接續實作。多 OA、審核協作及循環／檔案觸發排程仍見 [SaaS 規劃](SaaS平台與全站Tailwind改版規劃.md)，尚未實作。

## 組織與人員管理（Tailwind 主題）

1. 「組織管理」先選取或新增組織；右側資料只顯示目前選取的組織。
2. 在「人員與權限」新增後台人員，或將既有帳號加入組織。發送人員需另外按「設定授權」；一般 LINE 收件者不需要後台帳號。
3. 在「發送範圍」建立部門、專案或 LINE 群組，再回到人員旁勾選範圍、模組及報告。
4. 在「可用模組」查看組織開放的功能，透過「編輯組織」調整。帳號頁可搜尋姓名／Email／主要組織、依主要角色篩選。

新增組織後會自動選中；新增帳號和範圍會帶入該組織。新增表單提供角色說明，LINE 綁定收於選填進階設定。Cloudflare Access 的 Email 允許名單仍須另外維護，介面不會宣稱已驗證外部名單。

全站 UI 使用 Tailwind CSS 4 的主題變數與 CLI 本機編譯，無瀏覽器端 CDN 或全域 Preflight 重設。入口為 `styles/app.css`，整合既有基礎樣式、`workspace-theme.css` 與 `styles/management.css`，輸出為 `line-oa-archive/web/app.css`（部署時需包含）。修改來源後要重新建置；一般啟動不需要 Node.js：

```powershell
npm ci
npm run build:css
```

套件版本由 `package-lock.json` 固定，`node_modules` 不納入 Git。參考 [Tailwind CLI](https://tailwindcss.com/docs/installation/tailwind-cli) 與 [Theme variables](https://tailwindcss.com/docs/theme)。

LINE 官方帳號的對話紀錄與通知專案。目前已完成 Webhook、SQLite 對話紀錄、收件者管理、天氣訂閱及 PNG 圖片推送；每日排程提醒仍在規劃中。

## Windows 獨立控制台

第一次在專案根目錄執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-ControlPanel.ps1
```

安裝程式建立本專案的 `.venv`（需要 Python 3.11 以上及 Python Launcher），並安裝 HTTPS 憑證驗證使用的 `truststore` 、登入驗證使用的 `PyJWT[crypto]` 與圖片處理使用的 `Pillow`；不依賴其他專案的 Python 環境。它也會建立桌面「LINE 自動化控制台」捷徑及尚不存在的 `line-oa-archive/.env`，不覆蓋既有設定。

1. 雙擊桌面「LINE 自動化控制台」。開啟視窗只監看，不自動啟動服務。
2. 首次按「編輯 LINE 設定」，將 `LINE_CHANNEL_SECRET` 的範例值換成 LINE Developers → Basic settings 的 Channel secret，儲存並關閉記事本。
3. 按「啟動 LINE」。本機正常後，控制台會另行檢查公開連線；如果本機正常而公開未就緒，請檢查 Tunnel 路由。
4. LINE Webhook URL 使用 `https://reports.stack-base.com/webhook`。
5. 下班要停用時按「停止 LINE」。關閉控制台視窗不會停止背景服務；重新開機後需再次按「啟動 LINE」。

`.env` 的格式是每行 `KEY=value`，支援整行註解與值外層引號，不執行指令、不展開變數。啟動器與發送程式共用設定讀取，檔案值優先於繼承的同名環境變數。修改服務的 secret、token 或資料庫設定後請重啟 LINE。直接執行 `app.py` 仍使用環境變數，不自動載入 `.env`，也不啟動管理頁。多人收件名單存於 SQLite，不需要在 `.env` 逐一填 ID。

## 啟停範圍與狀態

- 本機服務：`http://127.0.0.1:18474`。公開網址：`https://reports.stack-base.com`。
- Cloudflare Tunnel 路由應將 `reports.stack-base.com` 指向 `http://127.0.0.1:18474`，路徑留白；Tunnel 與 Python 在同一台電腦執行。
- 控制台只管理本專案的 Python 服務，不啟停共用 Cloudflared、不修改 MultiThreader，也不修改遠端 Tunnel 設定。
- 本機狀態約每 3 秒檢查，公開連線約每 15 秒檢查。會核對程序身分、資料庫健康與本次啟動識別碼；「必要設定已填入」不代表 LINE 已驗證密鑰正確。
- `/healthz` 維持回傳 `ok`；`/_control/healthz` 提供無密鑰的健康識別資訊並禁止快取。公開路由需允許這兩個健康檢查路徑及 `/webhook`。
- 重複啟動不會建立第二份服務；由終端手動啟動或其他程序占用連接埠時，控制台不接管、不強制結束。
- 停止透過本機檔案通知服務停止接收新請求，等待進行中的請求與資料庫交易結束。預設等待 30 秒，逾時保留程序，待其完成；沒有對外的停止 API。
- `.env`、`.venv`、對話資料庫、備份及 `line-oa-archive/instance/` 的程序紀錄和日誌均不納入 Git。控制台「查看操作紀錄」只顯示操作摘要。

命令列也可操作：

```powershell
.\Start.ps1
.\Stop.ps1
.\Stop.ps1 -TimeoutSeconds 60
```

搬移資料夾後，先停止原服務，再於新位置重新執行 `Install-ControlPanel.ps1` 更新桌面捷徑。安裝不設定 Bot 開機自動啟動。

## 傳送天氣圖片到 LINE

### 多人使用：管理頁與自行訂閱

1. 啟動 LINE 服務後，從控制台「收件者與發送」、`Open-Recipients.ps1` 或已設定的遠端網址登入工作台。
2. 「工作總覽」顯示可用報告、有效收件者、天氣訂閱及進行中的工作；「報告中心」預覽 PNG、更新時間、大小與可見範圍。
3. 「建立發送」依序選報告、選聊天室、預覽確認；選人不會改變訂閱。非今日更新的報告需再次勾選確認，版本在送出前改變則拒絕發送。
4. 「收件者管理」可搜尋、篩選、分頁、編輯備註與公司／部門；完整 LINE ID 收在詳細資料中。公司及部門以名稱精確比對，請使用一致名稱。
5. 「天氣訂閱」管理長期通知名單。個人可私訊 Bot「訂閱天氣」「取消訂閱」「我的訂閱」「幫助」；群組由管理員設定。目前仍由管理員手動發送，尚無每日自動排程或其他主題訂閱。
6. 「發送紀錄」顯示最近 20 筆工作、操作人及逐聊天室結果；「帳號與設定」提供最近 50 筆操作紀錄。舊工作沒有操作人時會明確標示。

### 報告來源與員工權限

- 管理員可在報告中心新增或編輯 PNG 來源（1 MB 以內），指定公司及「全公司／指定部門／指定個人」範圍。檔案路徑只在設定來源時填寫；日常直接選報告。外部程式仍負責產圖，工作台不會代為執行任意程式。
- 預設天氣報告沿用 `.env` 的 `WEATHER_IMAGE_PATH`，定位為個人模組，預設僅管理員可見；可用 `WEATHER_OWNER_EMAIL` 指定擁有者，或以 `WEATHER_MODULE_ENABLED=false` 停用。其他報告依所屬公司、部門或指定 Email 在後端篩選及驗證。
- 總管理員可管理全部報告與發送；公司管理員僅管理所屬公司，員工只能查看獲授權報告，不能讀取收件者、發送紀錄、帳號設定，或呼叫任何管理寫入 API。
- 「帳號與設定」可新增、編輯、停用帳號與調整角色，公司／部門／個人範圍變更於後續請求生效，無須重啟服務。至少保留一位啟用中的管理員。
- 管理員可按右上角「切換視角」，選擇已啟用的員工來預覽公司／部門／個人報告。瀏覽器依實際登入帳號記住選擇，重新整理仍保留；上方提示列可一鍵返回管理員。每次 API 都重新驗證管理員與目標員工權限，預覽期間禁止管理操作。這不切換真正的 Cloudflare 帳號，也不延長登入期限；一般員工無此功能。
- 個人報告發送至 LINE 時，需將網站帳號連結到同公司的個人聊天室。公司／部門報表也會檢查收件者分類；權限或分類在排隊期間改變，尚未發送的對象會再檢查並取消不符合者。
- 預覽只由管理服務提供並驗證帳號權限；送到 LINE 的圖片仍使用既有高隨機性公開快照網址。此版本尚未提供圖片到期刪除或可撤銷分享，請在公司資料使用前評估這個傳遞方式。
- 新增員工後，仍需在 **Cloudflare Access 的 Allow／Emails 原則** 加入同一信箱；網站無法自動修改 Cloudflare 帳戶設定。

管理頁監聽 `127.0.0.1:18475`，與 `18474` Webhook／圖片服務分開。本機使用臨時管理憑證，服務重啟後需從控制台重新開啟管理頁。遠端使用須先完成下方 Cloudflare Access 設定；缺少設定時不接受代理連線。收到群組訊息不代表取得全部群組成員名單；要個別收件，使用者需與 Bot 互動。

### 在外面登入管理頁

1. Cloudflare Zero Trust → Access controls → Applications → Add an application → Self-hosted（介面也可能顯示 Self-hosted and private）。應用程式名称 `LINE 管理後台`，Public hostname 為 `line-admin.stack-base.com`，Path 留白，保護整個網域。
2. 設定 Allow 政策，Include → Emails 填入可登入管理員的完整信箱；不使用 Everyone 或 Bypass。登入方法啟用 One-time PIN（信箱驗證碼）。若未列出，先到 Zero Trust 的 Integrations → Identity providers 新增 One-time PIN。建議 Session duration 為 8 小時。
3. 複製 Access 應用程式的 Application Audience（AUD）與帳戶的 Team domain（`你的團隊.cloudflareaccess.com`），填入 `line-oa-archive/.env`：

   ```dotenv
   ADMIN_PUBLIC_HOST=line-admin.stack-base.com
   CF_ACCESS_TEAM_DOMAIN=你的團隊.cloudflareaccess.com
   CF_ACCESS_AUD=應用程式的AUD
   ADMIN_ALLOWED_EMAILS=你的完整信箱
   ```

   `ADMIN_ALLOWED_EMAILS` 現用於初次建立管理員（多個以逗號分隔），需同時加入 Access 政策。已有網站帳號不會因重啟而被重設角色或重新啟用。後續請從「帳號與設定」維護帳號，停用時在網站停用並移除 Access 許可；單獨移除 `.env` 的信箱不會刪除既有帳號。四項連線設定須完整填入；修改連線設定後重啟 LINE。本機會驗證 Access JWT 的 RSA 簽章、期限、issuer、audience，再查詢資料庫中的帳號及角色；不信任單獨的 Email 標頭。
4. 完成 Access 政策後，到 Tunnels → Bruce-PC-Services → Routes 新增已發佈應用程式路由：`line-admin.stack-base.com` → HTTP `127.0.0.1:18475`。Path 留白，HTTP Host Header 不要覆寫；保留 `reports.stack-base.com` 的 18474 路由。Access 僅保護管理網域，避免 Webhook 與 LINE 取圖被登入頁攔截。
5. 手機使用行動網路開啟 `https://line-admin.stack-base.com`，輸入允許的信箱，收取驗證碼登入。確認頁面上方顯示管理員信箱，再測試查閱名單。使用完成可按「登出」。到期時重新整理並登入；發送中斷先查紀錄，不自動重送。

電腦須保持開機、不進入睡眠、網路正常，LINE 本機服務與共用 Cloudflared 都須持續執行。遠端頁面的 PNG 路徑指的是這台 Windows 電腦上的檔案；不需要把圖片下載到手機。

官方說明：[建立 Access 應用程式](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)、[One-time PIN](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/)、[驗證 JWT 與取得 AUD](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)。

發送紀錄會逐一顯示 LINE 已接受、失敗、狀態不明或取消；相同工作識別碼不重複提交，不自動重送失敗或不明結果。訂閱發送在每一筆送出前再確認訂閱及有效狀態；已交給 LINE 的訊息無法因稍後取消訂閱而收回。停止服務會取消尚未送出的佇列並等待當筆請求結束。

要在天氣報告產生後傳送給訂閱名單，可執行：

```powershell
.\Send-WeatherReport.ps1 -Target subscribers
```

這會使用同一個管理服務與發送紀錄；不需要填個人或群組 ID。目前尚未建立每日自動排程，訂閱只決定每次發送時的收件者。

### 初次 LINE 後台設定與單一對象測試

1. LINE Developers → Messaging API：設定 Webhook `https://reports.stack-base.com/webhook`、按 Verify 並開啟 Use webhook。要測試群組時，啟用 Allow bot to join group chats，將 Bot 邀入測試群組。
2. 在同一頁的 Channel access token（long-lived）按 Issue；用控制台「編輯 LINE 設定」，將 token 貼到 `LINE_CHANNEL_ACCESS_TOKEN=` 後並儲存。Channel secret 用於接收驗證，不能代替 access token。
3. 向 Bot 的一對一聊天室與測試群組各傳一句「測試」，讓 Webhook 記錄 userId 與 groupId。
4. 控制台需已啟動 LINE，且公開連線正常。新增圖片服務程式後需重啟一次，日後產生新圖片不必重啟。

在 `D:\Tools\LINE_Automation` 執行：

```powershell
# 查看已收到訊息的個人與群組 ID，不發送訊息
.\Send-WeatherReport.ps1 -ListTargets

# 僅檢查圖片發布與外部讀取，不發送
.\Send-WeatherReport.ps1 -PrepareOnly

# 一對一聊天室與測試群組各傳一張
.\Send-WeatherReport.ps1 -Target both

# 也可只傳其中一邊
.\Send-WeatherReport.ps1 -Target user
.\Send-WeatherReport.ps1 -Target group
```

預設讀取 `D:\Tools\ai_weather_report\output\weather_report.png`；此指令不自動產生天氣報告。要更新報告，先執行天氣專案的 `run_weather.ps1`，確認圖片修改時間已更新後再發送。可用 `-ImagePath '其他 PNG 路徑'` 指定另一張圖片。

`-Target user/group/both` 保留給單一對象測試，未指定舊版固定目標設定時，資料庫必須各只有一個同類型聊天室。多人正式使用請改用管理頁，或 `-Target subscribers`。舊版 `LINE_PUSH_USER_ID`／`LINE_PUSH_GROUP_ID` 仍可讀取以維持相容，但不再是主要設定方式。

程式將圖片複製成 `published-images/` 中的隨機檔名快照，透過 `https://reports.stack-base.com/images/<隨機檔名>.png` 提供給 LINE。原圖更新不影響已發出的圖片；此目錄不納入 Git，也不提供目錄清單。持有完整網址者可讀取該圖片，不會公開其他專案檔案。已發送的圖片保留在本機，勿在 LINE 取圖前刪除。

本版原圖與預覽共用 PNG，限制 1 MB；大圖需先縮小。發送前會驗證公開 PNG 的內容與本機一致，HTTPS 使用作業系統憑證驗證，不關閉 TLS 驗證。LINE 回應成功只代表已接受請求，仍需在手機聊天室確認；封鎖 Bot 等情況不保證送達。失敗或逾時不會自動重送，避免重複通知；兩邊部分成功時，先查看輸出與聊天室，再單獨處理尚未成功的一邊。

官方參考：[圖片訊息](https://developers.line.biz/en/reference/messaging-api/#image-message)、[推送訊息](https://developers.line.biz/en/reference/messaging-api/#send-push-message)。

## 專案內容與驗證

管理介面的首頁放在專案最外層 `index.html`，樣式與互動程式保留在 `line-oa-archive/web/`。本機管理服務的 `/` 與 `/index.html` 都會載入這份首頁。日常請透過控制台「收件者與發送」或 `Open-Recipients.ps1` 開啟，讓管理憑證與 API 正常連線；直接雙擊 HTML 檔案只能查看靜態檔案，不能操作管理功能。

```text
LINE_Automation/
├─ index.html                 管理介面首頁
├─ ControlPanel.ps1           桌面控制台
├─ Open-Recipients.ps1        開啟管理介面
└─ line-oa-archive/
   ├─ admin_server.py         本機管理 API 與頁面服務
   └─ web/
      ├─ admin.css            樣式
      └─ admin.js             頁面互動
```

- [專案需求](專案需求.md)
- [Bot 功能與資料庫說明](line-oa-archive/README.md)
- [LINE OA 申請與設定](line-oa-archive/LINE_OA申請與設定.md)
- `line-bot-sdk-python/` 只供本機參考，不納入 Git。

```powershell
Push-Location line-oa-archive
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
Pop-Location
powershell.exe -NoProfile -STA -File .\ControlPanel.ps1 -SmokeTest
powershell.exe -NoProfile -File .\tests\control_lifecycle.ps1
```

測試使用臨時設定、資料庫與連接埠，不控制正式 Cloudflared 或 MultiThreader。

## 2026-09-30 改版驗證

首次啟動新版會新增報告來源、網站帳號、操作紀錄資料表，以及公司／部門、發送操作人等欄位，保留原有資料。正式套用前已使用 SQLite backup 建立 `backups/before-workspace-*.db` 備份；備份不納入 Git。

新增驗證涵蓋公司／部門／個人報告隔離、直接 API 越權、帳號停用、管理員保留、資料遷移、報告變更及發送時範圍重查。桌面、手機、員工視角的瀏覽器測試使用獨立臨時資料庫與模擬發送。

瀏覽器測試需要可用的 Playwright 與 Chrome：

```powershell
# 已安裝 @playwright/test 時直接執行；也可用 PLAYWRIGHT_MODULE 指定既有套件的絕對路徑。
node tests/workspace_browser.cjs
```

媒體接收與 Hash 去重、多主題訂閱、每日循環排程、工具程式執行及 Ubuntu 部署仍列於需求／後續階段，並未隨 UI 改版自動啟用。

## 訊息預約與個人模組（2026-09-30）

- 右上角保留「視角切換」，不儲存第二組 Cloudflare 登入憑證。
- 天氣程式是獨立個人模組，沿用既有產圖路徑與訂閱；不預設共享給全體員工，也不代表公司報表。
- 「建立發送」可輸入文字（最多 5000 UTF-16 單位），或選擇報告 PNG；選對象後，於確認頁選擇立即傳送或指定台北日期時間。
- 預約至少 30 秒後、最遠一年；固定保存當下文字／圖片快照及收件者。發送紀錄列出所有待發預約與最近 20 筆其他工作，可取消尚未開始的預約；修改時請取消後重建。
- 排程保存在 SQLite，服務每兩秒檢查；重啟保留未到期預約。電腦、網路及 LINE 服務須運作，逾期超過 10 分鐘不補發。到期時重新驗證操作人、收件者與報告權限、訂閱狀態。
- 預約由本專案執行，不會同步顯示在 LINE OA 原生後台。尚未提供每日／每週循環、草稿庫或混合多則訊息編輯。
- LINE 使用者識別與限制見 [LINE OA使用者識別研究.md](LINE%20OA使用者識別研究.md)。

## 公司與模組權限（2026-09-30）

| 角色 | 模組與資料 | 可操作內容 |
| --- | --- | --- |
| 總管理員 | 全部公司、全部報告與個人模組 | 設定帳號角色、公司歸屬、報告來源與權限；管理全部發送 |
| 公司管理員 | 僅所屬公司的報告、收件者、公司發送紀錄與預約 | 預覽／立即或預約發送本公司報告與文字、取消本公司預約、維護收件者備註與部門 |
| 員工 | 自己公司內獲授權的公司／部門／個人報告，以及明確授予的個人模組 | 檢視報告；禁止管理寫入 |

- 既有 `administrator` 角色現在顯示為「總管理員」，不更動原帳號權限。新增 `company_admin` 角色；公司管理員及員工皆必填公司，名稱使用一致的完整值。
- 由總管理員在「帳號與設定」編輯角色及公司；在報告來源指定所屬公司與可見範圍。公司管理員無法修改帳號角色、公司歸屬或伺服器檔案路徑。
- 公司管理員看不到預設個人天氣模組及其訂閱功能，除非明確授予個人模組擁有者身分；不會因為有「管理員」角色就自動取得全部模組。
- 總管理員可預覽公司管理員／員工；公司管理員只可預覽本公司員工。所有預覽皆禁止寫入與真實發送。
- 公司隔離由 API 執行，包含直接查詢報告與工作 ID、篩選帳號／操作紀錄，以及發送對象與取消預約。預約執行前會重新查核操作人的現行角色與公司。
- 工作保留建立時的公司範圍。舊版未記錄公司之工作僅總管理員可見，不依現行帳號公司推測歷史歸屬。

## 組織管理與多組織身分（2026-09-30）

目前後台角色名稱統一為「平台管理員／組織管理員／發送人員」；一般收件者只使用 LINE，不需後台帳號。前面的公司說明為先前版本；目前公司、單位、社團、俱樂部與個人工作室均以組織管理。

1. 平台管理員進入「組織管理」建立名稱、類型，勾選報告中心、訊息發送與預約、天氣模組授權。天氣預設不授權。
2. 在「帳號與設定」建立登入帳號與主要組織；再用「組織管理 → 新增成員資格」分別授予其他組織的角色、部門與 LINE 個人聊天室。
3. 成員登入後，可在右上角組織選單切換自己已啟用的組織。同一人可在 A 為組織管理員、B 為發送人員；瀏覽器記住選擇，後端每次重新驗證。
4. 平台管理員保持全平台管理視角，可用「切換視角」預覽指定成員及組織；預覽仍禁止寫入與發送。
5. 報告來源及收件者的組織欄位改用組織選單。組織名稱可修改，識別碼固定；停用組織或模組、撤銷成員資格會作用於後續請求及尚未執行的預約。

資料遷移只執行一次：既有公司名稱轉成組織記錄，原角色、部門、LINE 連結轉成初始成員資格。既有資料的內部 `company` 欄位保留作為組織識別碼，以維持歷史相容；新組織使用隨機識別碼。組織改名不修改歷史資料鍵，也不會重啟後恢復撤銷的成員資格。

模組範圍：報告中心授權組織內的既有報告來源，天氣授權內建個人天氣模組的查看權；訊息模組允許組織管理員操作文字／報告發送。一般成員沒有直接後台登入資格；舊帳號保留，管理員仍可唯讀預覽。這不是任意外部程式的安裝與執行器。


## 選檔與 LINE 圖片訊息（2026-09-30）

- 「建立發送」新增單圖／多圖、圖文卡片、輪播卡片、圖文訊息四種圖片格式；可直接開啟裝置檔案視窗，選擇 JPG／PNG、預覽、排序、移除及設定連結。
- 單圖／多圖最多五張；Flex 輪播最多十二張卡片；圖文訊息提供 1／2／4／6 區的 HTTPS 點擊連結。各格式皆可選擇對象與立即／單次預約發送。
- 「報告中心 → 新增報告來源／設定來源」也提供選檔上傳。每日自動更新的固定路徑移至可展開的進階設定。
- 選檔每張最多 8 MiB JPG／PNG，會轉正、縮圖、必要時減色並保存 PNG 副本；上傳檔不會自動追蹤原始裝置的修改。
- 組織素材與收件者需屬於同一組織。上傳檔在確認發送前不公開；預約保存內容快照，執行時重查權限。
- 格式對照、資料保存、操作限制與後續項目見 [LINE訊息格式與編輯器設計.md](LINE訊息格式與編輯器設計.md)。


## 工作台視覺風格

介面參考 Apple iOS／macOS：淺色側欄、系統字體、圓角卡片與控制項、分段選擇，以及手機抽屜導覽和底部表單。使用低飽和綠色相近色、保留主色 `#00B900` 與 AA 文字對比要求。設計、響應式行為及驗證記錄見 [UI風格與元件規範.md](UI風格與元件規範.md)。


## 發送人員與收件範圍（2026-09-30）

一般 LINE 收件者不需要 Email 登入或 Cloudflare Access 白名單。後台僅供平台管理員、組織管理員及被授權的發送人員操作；小組長、部門主管與專案主管可使用「發送人員」角色。

平台管理員設定步驟：

1. 在「收件者管理」指定聊天室所屬組織、部門。
2. 在「帳號與設定」建立角色為「發送人員」的登入帳號，指定主要組織；需要跨組織時，再於「組織管理」新增成員資格。遠端登入仍須在 Cloudflare Access 允許該 Email。
3. 在「組織管理 → 發送範圍」新增部門、專案或群組範圍。部門依分類動態比對；專案可勾選多個個人／群組；群組只指定一個聊天室。
4. 在同頁「發送人員授權 → 設定授權」勾選可用模組、可發送範圍（可複選）及報告。新帳號預設無權限；只發文字或自訂圖片可不選報告。
5. 可使用右上角「切換視角」檢視發送人員看到的內容。預覽仍為唯讀；實際發送須使用本人登入。

發送人員只能使用已授權對象、報告及本人素材，只看目前組織內本人且對象仍獲授權的工作；不能改收件者分類或帳號權限。報告原有部門／個人限制仍會與發送範圍共同檢查。組織管理員保留整個組織的既有權限。

個人報告可直接選擇 LINE 個人收件者，無需為對方建立網站帳號。舊的帳號綁定保留相容；既有一般成員帳號不會自動升權，現在不能直接登入後台。

撤銷授權、停用範圍或改變收件者歸屬後，預約送出前重新檢查，失效的傳送會取消。檔案／資料夾變更自動推送仍未實作。

## 收件者名稱自動更新

收到 LINE 使用者／群組事件後，背景會自動查詢名稱；啟動時也補查既有名單，不需逐一按「更新 LINE 名稱」。成功名稱快取 24 小時，查詢失敗會延後重試，不影響訊息保存。手動備註不被覆蓋，畫面優先顯示備註；補名完成後重新整理頁面即可看到結果。管理員仍可手動更新名稱。此功能需有效的 Channel access token，並以 LINE API 能取得的資料為限。

## 移除報告

平台管理員可在「報告中心」卡片按「移除報告」，確認後移除來源並取消其尚未開始的發送工作。保留原始圖片、訂閱名單及歷史紀錄；已開始或已送出的訊息不能撤回。內建天氣報告也可移除，設定對所有組織生效且重啟後保留；報告中心提供「恢復天氣報告」，但不會恢復已取消的工作。本機停用天氣模組時須先啟用才能恢復。一般來源移除後需重新新增；目前為單筆操作，批次清除與對話重置尚未實作。
