# Facebook counters: final live validation หลังจำกัด target scope — 18 ต.ค. 2026

รอบสุดท้ายของ [issue #8](https://github.com/PeeraphatN/social-lisening/issues/8) เก็บ live บน P01–P10 แบบ anonymous ไม่มี login, proxy หรือการหลบ challenge หลักฐานทั้งหมดอยู่ใน ignored `runs/` ที่เครื่อง local

## อัปเดตล่าสุด

- เก็บ final run ครบตามแผน: session `counter-scope-final-20261018T202456Z` เริ่ม 2026-10-18T20:24:56Z จบ 2026-10-18T20:28:38Z (เวลา UTC)
- ผ่านคิว anonymous เดียว ไม่มี retry เว้นอย่างน้อย 20 วินาทีระหว่าง URL (`requested_at` ห่างกันจริง 22–37 วินาที)
- main navigation ได้ HTTP 200 ครบ 10/10 ไม่เจอ 403/429, CAPTCHA/challenge หรือ stop condition (`stop_reason` ว่าง)
- SHA-256 ของ source ตรงกันก่อนและหลัง run ทั้ง run วัดจาก implementation เดียวกัน:

```text
probe_post.py       81b1b80a34156db6980dc46994e787213e71d7d82a3151ad30b298f95b128a86
inspect_browser.py  eab416e00f57d3398424928951d8e4f19c3f046c7cc8a38292dc38a52c6b5e63
score_counters.py   cb1c1b27c628e8d4b5f5da07cf12a77fd3ee4f28d4cf900a46e1085b6fe2868a
```

## ผลที่ได้

coverage หลังจำกัด target scope แบบเข้มงวด เหลือ 11/30 ช่องที่อ่านได้ ทุกช่องมาจาก identity-scoped embedded JSON (`embedded_ufi_summary`/`embedded_comment_summary`) ไม่มีสักค่าเดียวที่มาจาก body

| Metric | อ่านได้ | `null` |
| --- | --- | --- |
| Reaction | 0/10 | 10 |
| Comment | 6/10 | 4 |
| Share | 5/10 | 5 |

ผลต่อ sample (scope status ในวงเล็บ):

| Sample | HTTP | Reaction | Comment | Share |
| --- | --- | --- | --- | --- |
| P01 | 200 | `null` (missing) | `null` (missing) | `null` (missing) |
| P02 | 200 | `null` (missing) | 374 (identity_scoped_fallback) | 353 (identity_scoped_fallback) |
| P03 | 200 | `null` (missing) | 4 (identity_scoped_fallback) | 0 (identity_scoped_fallback) |
| P04 | 200 | `null` (missing) | 1 (identity_scoped_fallback) | 414 (identity_scoped_fallback) |
| P05 | 200 | `null` (conflicting) | 77 (identity_scoped_fallback) | 79 (identity_scoped_fallback) |
| P06 | 200 | `null` (missing) | `null` (missing) | `null` (missing) |
| P07 | 200 | `null` (missing) | `null` (missing) | `null` (missing) |
| P08 | 200 | `null` (missing) | `null` (missing) | `null` (missing) |
| P09 | 200 | `null` (missing) | 30 (identity_scoped_fallback) | 3 (identity_scoped_fallback) |
| P10 | 200 | `null` (missing) | 0 (identity_scoped_fallback) | `null` (missing) |

P03 Share=0 กับ P10 Comment=0 คงเป็น explicit zero พร้อมหลักฐาน (count, raw, exact_count, feedback ID ที่ตรวจแล้ว) ไม่ถูกแปลงเป็น `null` และไม่ถูกนับเป็น error ศูนย์ใน accuracy

คู่ exact ที่เทียบได้จาก page session เดียวกันมี 4 คู่ ทุกคู่ error เป็น 0:

| คู่ | collector | reference | signed/absolute/percentage error |
| --- | --- | --- | --- |
| P03 Comment | 4 | 4 | 0 / 0 / 0.0 |
| P09 Comment | 30 | 30 | 0 / 0 / 0.0 |
| P04 Share | 414 | 414 | 0 / 0 / 0.0 |
| P09 Share | 3 | 3 | 0 / 0 / 0.0 |

ส่วนที่อ่านได้อีก 7 ช่อง (Comment P02/P04/P05/P10, Share P02/P03/P05) ยังไม่มี reference ใน session นี้ จึงเป็น missing reference ไม่ใช่ error; ฝั่ง reference ที่ยังไม่มีคู่มี 21 รายการ เทียบแล้ว 4 รายการ ที่เหลือ 17 รายการ collector ยังอ่านไม่ได้

## ที่เจอ

- body counters ยัง unsupported บนทุก layout ทั้ง 10 ตัวอย่าง ตัว rendered header/permalink ของ container พิสูจน์ไม่ได้ว่าชี้ที่ resolved route ที่แท้จริง URL ที่ขอเป็น `share/p` แล้ว resolve ไป `posts/pfbid…`/`story.php` ผ่าน canonical alias กับพารามิเตอร์ `rdid` scope จึงไม่เคยถึง `target_scoped` ค่าจาก body คง `null` ทั้งหมดตาม fail-closed rule
- P05 ยังเป็น `preview_only` Reaction scope เป็น `conflicting` นับเป็น unverified 1 ช่องใน score ไม่ใช่ missing
- P06/P07/P08 มี embedded comment summary (3/542/2) เก็บไว้ใน `comment_counter_evidence` แต่บน `story.php` ยอดบวกยังไม่รับ คง `null` ไว้ รับเฉพาะ explicit zero (P10)
- coverage เดิม 29/30 มาจาก body scan ทั้งหน้า วิธีนั้นอ่านยอดจากโพสต์อื่น คอมเมนต์ หรือ preview ในหน้าเดียวกันได้ ตัวเลขเก่าจึงเทียบกับผลใหม่ตรง ๆ ไม่ได้ การอ่านได้ครบเป็นเรื่อง coverage ไม่ใช่ accuracy

## แก้แล้ว

- body counters ต้องมาจาก rendered container เดียวที่พิสูจน์ได้ว่าผูกกับ requested/resolved route ถ้าไม่มี candidate มีหลายตัว หรือขัดกัน คืน `null` ไม่หยิบค่าแรกหรือค่าที่มากที่สุด
- ทุก metric มี `*_scope_status` แยก `target_scoped`, `identity_scoped_fallback`, `ambiguous`, `missing`, `conflicting` พร้อม `*_count_source`, `*_body_evidence`, `*_counter_evidence` ไว้ตรวจย้อนหลัง
- กติกา null-vs-zero: 0 แท้ต้องมาจาก target-scoped body text หรือ identity-scoped summary ที่สอดคล้องภายใน (Share ต้องมี `is_empty` boolean ตรงกับ count) label ที่หายไปไม่สร้างศูนย์ปลอม
- `score_counters.py` แยก exact/approximate/zero/missing/unverified ออกจากกัน คิด signed/absolute/percentage error เฉพาะคู่ exact จาก session เดียวกัน และตัด percentage error เมื่อ reference เป็น 0
- offline suite ผ่าน 98/98 tests กับ source ชุดเดียวกับที่ใช้เก็บ live

## ยังไม่สรุป

- reference ของรอบนี้ 21 รายการ ได้มาจาก unique rendered labels ใน body text ของ snapshot เดียวกัน (เช่น `ความรู้สึกทั้งหมด 170`, `72 ความคิดเห็น`, `แชร์ 76 ครั้ง`) ยังรอผู้ใช้ยืนยัน จึงยังไม่อ้าง accuracy แบบ human-verified และยังไม่ตั้ง tolerance
- error 0 ทั้ง 4 คู่พิสูจน์แค่ consistency ระหว่าง embedded summary กับ label ที่ render ใน snapshot เดียวกัน ไม่ใช่ความถูกต้องของ Facebook ทุก layout
- Reaction อ่านได้ 0/10 และ body counters ยังไม่มี layout ไหนที่พิสูจน์ target scope ได้เลย

## งานต่อ

- ให้ผู้ใช้ตรวจ references 21 รายการใน `runs/counter-scope-final-20261018T202456Z-references.json` แล้ว re-score จาก evidence เดิมได้ ไม่ต้องเปิด Facebook ซ้ำ
- ถ้า references ผ่าน ประกาศผล accuracy ของ 4 คู่ exact เป็นทางการใน issue แล้วค่อยตัดสินใจเรื่อง tolerance
- หาสัญญาณที่เสถียรกว่าสำหรับพิสูจน์ rendered target container (เช่น header ที่ผูก route ได้) ก่อนคิดเปิด body counters ใน layout ใด ๆ
- ปิดเกณฑ์ counter-scope ของ #8 ด้วยผลชุดนี้ พร้อมระบุ scope ที่ทดสอบไว้ใน issue #6 ว่าไม่ใช่ coverage ทุก layout ของ Facebook