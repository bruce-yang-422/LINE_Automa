"""所有數量上限的唯一定義處（單台 PC 規模）。

各模組一律 `import limits` 引用，不得在程式中另寫數字；前端顯示「目前數量／上限」
時由 API 回傳這裡的值。規格出處標在每一項後方。
"""

# 聯絡對象與標籤（聯絡人管理規格 12.3）
TAGS_PER_OA = 100
TAGS_PER_CONTACT = 10
BULK_CONTACTS = 200
SAVED_FILTERS_PER_OA = 10              # 聯絡人管理規格 13.2

# 對話記事本（對話記事本管理規格 9 與 10）
NOTES_PER_ROOM = 100
PINNED_NOTES_PER_ROOM = 5
NOTE_TAGS_PER_OA = 30
TAGS_PER_NOTE = 5
NOTE_CONTENT_MAX = 2000
NOTE_TRASH_DAYS = 30
NOTE_CATEGORIES_PER_OA = 50

# 聊天（聊天規格 12.3、12.5、14）
CANNED_REPLIES_PER_OA = 100
SCHEDULED_MESSAGES_PER_OA = 50
TEXT_MESSAGE_MAX = 5000                # LINE 文字訊息上限
MESSAGES_PAGE_SIZE = 50
ROOMS_PAGE_SIZE = 50
RESPONSE_HOLIDAYS_MAX = 100
SINGLE_MEDIA_MAX_BYTES = 20 * 1024 * 1024          # 20 MB
TOTAL_MEDIA_MAX_BYTES = 10 * 1024 * 1024 * 1024    # 10 GB
MEDIA_RETENTION_DAYS = 365

# 案件、範本包與分類（案件管理流程規格 16、17）
CASE_EXPORT_MAX = 5000
CATEGORIES_PER_OA = 20                 # 記事類型與案件類別各自上限
CUSTOM_PACKS_PER_WORKSPACE = 20
TEMPLATES_PER_PACK = 20                # 案件範本與記事範本各自上限


def as_dict() -> dict:
    """供前端顯示「目前數量／上限」使用。"""
    return {k: v for k, v in globals().items() if k.isupper() and isinstance(v, int)}
