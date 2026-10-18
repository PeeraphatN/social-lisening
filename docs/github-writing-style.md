# GitHub issue/comment writing style

Use this when writing GitHub issues or comments for this repo.

## Voice

Write like the project owner taking working notes, not like an agent audit log.

Good tone:

- concise, direct, practical
- Thai is OK; use technical English terms when clearer
- enough detail for future-you to continue work quickly
- caveats kept, but written plainly

Prefer phrases like:

- รอบนี้ลอง...
- ผลที่ได้...
- ที่เจอ...
- แก้แล้ว...
- ยังไม่สรุป...
- งานต่อ...

Avoid:

- agent/report tone
- legalistic phrasing
- excessive caveats
- long paragraphs that mix result, caveat, fix, and next step
- repeating “ไม่ถือว่า”, “ไม่อ้างว่า”, “ยังไม่สามารถสรุปได้” too often

## Default comment structure

Use only the sections that fit the update.

```md
## อัปเดตล่าสุด

...

## ผลที่ได้

...

## ที่เจอ

...

## แก้แล้ว

...

## ยังไม่สรุป

...

## งานต่อ

...
```

## Rewrite examples

Bad:

> ผลนี้ไม่ถือเป็น ground truth พร้อมกันและไม่ควรอ้างเป็น coverage ของ Facebook ทั้งหมด

Good:

> reference จากผู้ใช้ไม่ได้ดูพร้อม snapshot เดียวกัน เลยใช้เป็น confirmation คร่าว ๆ ก่อน

Bad:

> ยังไม่พร้อมสรุปว่า deploy-ready

Good:

> ยังไม่พร้อมปล่อย เพราะ scope กับ missing value ยังไม่นิ่ง

Bad:

> การหยิบยอดผิดโพสต์ยังเป็นข้อผิดพลาด ไม่ใช่ความคลาดเคลื่อนที่ยอมรับได้

Good:

> ถ้าหยิบเลขผิดโพสต์คือ bug ไม่ใช่ tolerance

## Final check before posting

Before posting an issue/comment, check:

- Can I tell what happened in 10 seconds?
- Are result, caveat, fix, and next step separated?
- Did I keep the important uncertainty without sounding like an audit report?
- Would this help me continue the work next week?
