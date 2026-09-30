# LINE OA：回傳訊息與使用者識別

研究日期：2026-09-30。依 LINE Developers 官方文件；以下區分 API 能力與本專案已實作項目。

## 收到訊息時能知道什麼

| 資料 | 來源 | 用途與限制 |
| --- | --- | --- |
| `userId` | Webhook 的 `source` | 系統辨識發話者；不是使用者手動設定、可搜尋的 LINE ID。部分未同意取得資料的情況會缺少。 |
| `source.type`、`groupId`／`roomId` | Webhook | 區分一對一、群組、舊式多人聊天室；群組 ID 和發話者 ID 應分開保存。 |
| 訊息 ID、類型、內容、時間 | Webhook 的 `message`、`timestamp` | 文字可直接取得；圖片、影片等需以訊息 ID 另外下載，不能只記錄 ID 就當作已保存附件。 |
| 引用的訊息 ID | 適用訊息的 `quotedMessageId` | 可關聯引用訊息；不代表能判定檔案第一次由誰建立或轉傳。 |

來源：[取得使用者 ID](https://developers.line.biz/en/docs/messaging-api/getting-user-ids/)、[接收 Webhook](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)、[群組與多人聊天室](https://developers.line.biz/en/docs/messaging-api/group-chats/)。

## 可另外查詢的資料

| 情境 | API | 回傳的辨識資訊 |
| --- | --- | --- |
| 個人資料 | `GET /v2/bot/profile/{userId}` | `displayName`、`pictureUrl`、`statusMessage`、`language`、`userId`；選填資料可能缺少。 |
| 群組中的發話者 | `GET /v2/bot/group/{groupId}/member/{userId}` | 顯示名稱、使用者 ID、頭像；不能假定也有個人狀態文字與語言。 |
| 群組本身 | `GET /v2/bot/group/{groupId}/summary` | 群組 ID、群組名稱、群組圖片。 |

需符合端點的存取條件，例如 Bot 位於該群組且已知成員 ID；API 可能因封鎖、離群或同意狀態等原因失敗。不能將查不到資料解讀為某個員工不存在。

來源：[Messaging API 參考：個人資料](https://developers.line.biz/en/reference/messaging-api/#get-profile)、[群組成員資料](https://developers.line.biz/en/reference/messaging-api/#get-group-member-profile)、[群組摘要](https://developers.line.biz/en/reference/messaging-api/#get-group-summary)。

## 普通傳訊息不會提供的身分資料

一般 Messaging API 個人資料不包含 Email、電話、真實姓名、員工編號、所屬公司、住址或生日。Email 需另外使用 LINE Login 並取得所需權限與使用者授權；電話等進一步資料涉及不同產品與資格，不是收到 OA 訊息就有。

顯示名稱可自行修改、可以重名，頭像也不是公司身分證明。不可用名稱相似或頭像相同自動授予員工／管理員權限。

來源：[官方使用者資料能力比較](https://developers.line.biz/en/docs/basics/user-profile/)。

## 建議本專案怎麼辨識人

1. 以 Provider 範圍內的 `userId` 作為 LINE 身分鍵，名稱、頭像及內部備註作為顯示資訊。同一 Provider 下不同類型 Channel 的同一使用者 ID 相同；不同 Provider 不可假設可直接合併。[官方說明](https://developers.line.biz/en/docs/messaging-api/getting-user-ids/)
2. 網站登入帳號、公司／部門、員工編號另行管理，不由 LINE 暱稱推測。
3. 後續可建立「已登入員工產生短效單次綁定碼 → 私訊 Bot → 伺服器連結網站帳號與 LINE userId」流程。綁定碼需限時、限次、避免猜測；不可在群組接受身分綁定。這是建議設計，尚未實作。
4. 群組是多人共用的發送目標，不等同個人帳號；群組中的訂閱或發話不能讓整個群組取得該人的私人報告。

## 目前程式實況

- `line_messages` 已保存發話者 ID、聊天室 ID／類型、訊息 ID／類型、文字及時間；撤回訊息另記撤回時間。
- 收件者管理「更新 LINE 名稱」目前保存個人顯示名稱或群組名稱；尚未保存頭像、狀態文字、語言，也沒有完整群組成員名冊介面。
- 現在可由管理員手動連結網站帳號與個人 LINE 聊天室；尚無自助綁定碼驗證。
- 附件下載與 Hash 去重仍依 `專案需求.md` 待實作。

## 與預約發送的關係

本次單次預約使用本專案資料庫與本機排程器，到期呼叫 Messaging API；不是把工作交給 LINE OA 後台。預約中的收件者用聊天室 ID 固定保存，顯示名稱只供確認；到期仍重新檢查有效性與權限。
