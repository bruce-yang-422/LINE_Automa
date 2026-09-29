# LINE 自動化

LINE 官方帳號的對話紀錄與通知專案。目前已完成 Webhook、SQLite 對話紀錄、收件者管理、天氣訂閱及 PNG 圖片推送；每日排程提醒仍在規劃中。

## Windows 獨立控制台

第一次在專案根目錄執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-ControlPanel.ps1
```

安裝程式建立本專案的 `.venv`（需要 Python 3.11 以上及 Python Launcher），並安裝圖片發送所用的 `truststore`；不依賴其他專案的 Python 環境。它也會建立桌面「LINE 自動化控制台」捷徑及尚不存在的 `line-oa-archive/.env`，不覆蓋既有設定。

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

1. 啟動 LINE 服務，按控制台 **「收件者與發送」**，或執行根目錄 `Open-Recipients.ps1`。
2. 管理頁顯示已知的個人與群組；按「更新 LINE 名稱」取得顯示名稱，也可填寫備註後按該列「儲存」。既有訊息紀錄會自動帶入名單，後續由加好友、加入群組與訊息 Webhook 登記新收件者。
3. 勾選多個對象，按 **「發給勾選對象」**。這是一次性手動選取，不會改變訂閱狀態。
4. 勾選某列的「天氣訂閱」並儲存，即加入訂閱名單；按 **「發給天氣訂閱名單」** 傳給目前仍有效的訂閱者。群組訂閱由管理員設定，單一成員在群組傳指令不會改動整個群組。
5. 個人可私訊 Bot「訂閱天氣」「取消訂閱」「我的訂閱」「幫助」，Bot 會記錄並回覆目前狀態。重送的同一則訊息不會重複處理；封鎖 Bot 或 Bot 離開群組後會停用對象並取消訂閱。

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

   多名管理員信箱以逗號分隔，且同時加入 Access 政策。四項必須完整填入；修改後在控制台按「重啟 LINE」。本機會驗證 Access JWT 的 RSA 簽章、期限、issuer、audience 及 Email 白名單；不信任單獨的 Email 標頭。憑證驗證金鑰透過 HTTPS 取得並暫存。
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
