# Facebook counters: P03 Share และ same-version repeat — 12 ต.ค. 2026

ทำต่อจาก [accuracy issue #6](https://github.com/PeeraphatN/social-lisening/issues/6) เก็บข้อมูลแบบ anonymous ไม่มี login, proxy หรือการหลบ challenge

## ยืนยันเพิ่มเติม

หลังจบรอบทดลอง ตรวจต้นทางแล้ว **P03 ไม่มีการแชร์: reference Share=0** ตรงกับ embedded `share_count=0/is_empty=true` ของ story ที่ตรวจ identity แล้ว

ผล collector ใน snapshot เดิมยังเป็น `null` เพราะตอนนั้น opaque-pfbid fallback ยังไม่รองรับ ไม่แก้ผลย้อนหลังหรือเปลี่ยน coverage 29/30 เป็น 30/30 และไม่ได้บันทึกเวลาหรือ surface ของ reference ครั้งนั้น

บันทึกแยกใน `runs/p03-share-user-confirmation.json` ข้อความด้านล่างเป็นหลักฐานและการตัดสินใจ ณ เวลาทดลองก่อนรับ confirmationนี้

## ปัญหา

- P03 Reaction/Comment อ่านได้ แต่ Share เป็น `null`
- หลังแก้ P02/P05 icon counters ยังมี live เพียงรอบเดียว จึงต้องแยกการเปลี่ยนยอดตามเวลาจากความสม่ำเสมอของ extraction

## Reproduce และ fail path

Replay P03 จาก `accuracy-20261012T061229Z-r1`, `-r2` และ `accuracy-postfix-20261012T081729Z` ได้ Reaction24/Comment1/Sharenull ทั้งสามชุด Body ไม่มี Share counter; embedded UFI มี `share_count={count:0,is_empty:true}` และ `i18n_share_count="0"`

Debugger หยุดที่ URL guard ของ `extract_icon_counters`: URL `/armymidecal/posts/pfbid...` ไม่เข้า photo/group numeric-ID mapping ทำให้ `ids=[]` แล้ว return `{}` ก่อนอ่าน JSON ตัว body parser จึงไม่มี fallback ที่รองรับรูปแบบนี้

## ทดลองหักล้างสมมติฐาน

| สมมติฐาน | หลักฐาน/ผล |
| --- | --- |
| Parser พลาด label Share ที่แสดง | ไม่พบ label ใน body P03 ทั้ง3ชุด; P04 มี label และอ่าน406/407/407ได้ |
| URL guard หยุด structured fallback | ยืนยันด้วย debugger: `ids=[]` แล้ว return `{}` |
| Zero เป็นของโพสต์อื่น เพราะ canonical pfbid ไม่เหมือน URL ที่ขอ | ไม่ใช่ข้อสรุปที่ถูกสำหรับชุดนี้: route metadata เชื่อม URL ที่ขอกับ storyID และ feedback ได้ครบ; P04 ก็มี pfbid ต่างกัน |
| `shareable_from_perspective_of_feed_ufi=null` แปลว่าแชร์ไม่ได้/ยอดต้อง0 | หักล้างได้: P04 มีค่าnullเหมือนกัน แต่มี Share406/407/407 |
| `is_empty=true` ทำให้ browser ไม่แสดง0 | สอดคล้องกับ snapshot แต่ยังไม่พิสูจน์ semantics ของ Facebook หรือยอดที่ผู้ใช้มองเห็น จึงไม่ใช้เติม0 |

### Identity ที่ตรวจได้ offline

แต่ละ snapshot มี chain ที่ผ่านครบหนึ่งชุด:

`initialRouteInfo.route.url == requested path` → `rootView.props.storyID == node_v2.id` → nested UFI story ID/post ID → outer/inner feedback ID == base64(`feedback:{post_id}`) และ subscription target ID ตรงกัน

P03 post ID: `28579474408384507`; P04: `1055199960829018` พบ incomplete story fragments อีก2ชุดต่อ snapshot ซึ่งไม่ผ่าน chain และไม่ได้ใช้เป็นหลักฐาน

Identity ตรวจได้แล้ว แต่ยังไม่มีหลักฐานว่าค่า embedded0 คือ Share counter ที่ browser แสดง Screenshot มี anonymous login overlay จึงไม่ใช้ยืนยันว่ามองเห็น counterครบทุกตัว ไม่ปิด popupหรือเปลี่ยน session

## ตัดสินใจ/การแก้

คง P03 Share=`null` ตาม browser-displayed contract ไม่เพิ่ม opaque-pfbid fallback เพียงเพื่อเปลี่ยน coverageเป็น100% ไม่แก้ extraction code ในรอบนี้

เพิ่ม `experiments/facebook_posts/test_pfbid_share.py` จำนวน6 tests เพื่อล็อกข้อจำกัด: route-scoped hidden0, positive summaryที่ยังไม่รองรับ, routeอื่น, story/summaryขัดกัน, summaryหาย และ body Shareที่แสดงต้องชนะ embedded0 Tests เหล่านี้ตรวจพฤติกรรมปัจจุบัน ไม่ได้อ้างว่า implement route identity resolverแล้ว

Suite42/42ผ่านก่อนเริ่ม live repeat

## Same-version live repeat

Session: `counter-repeat-20261012T085728Z`

- ตรึง SHA-256 ของ `probe_post.py` และ `inspect_browser.py`; ตรวจซ้ำก่อน/หลังแต่ละ URL
- เปิด anonymous browser URLละหนึ่งครั้ง 10โพสต์×2รอบ ผ่านคิวเดียว ไม่มี retries
- เว้นอย่างน้อย15วินาทีระหว่างจบคำขอกับคำขอถัดไป; เว้น600วินาทีหลังจบรอบแรก
- หยุดเมื่อพบ403/429, CAPTCHA/challenge, HTTPอื่นที่ไม่ใช่200, request failure หรือ source hashเปลี่ยน
- บันทึก parsed/raw/source/evidence/time แยกจาก referencesเก่า ไม่ถือว่าตัวเลขข้ามรอบต้องเท่ากัน

ผล: เก็บครบทั้งสองรอบแล้ว

| รอบ | เวลาไทย | HTTP200 (main navigation) | Counterที่อ่านได้ |
| --- | --- | --- | --- |
| 1 | 15:57–16:00 | 10/10 | 29/30 |
| 2 | 16:10–16:13 | 10/10 | 29/30 |

ช่วงระหว่างคำขอจริงอย่างน้อย15.001098วินาที; ช่องว่างระหว่างรอบ600.001566วินาที ไม่มี retry หรือ stop conditionที่ตรวจพบ เปิด URLรวม20ครั้ง ไม่ใช่จำนวนHTTP requestsทั้งหมดที่ browserโหลด

| Sample | รอบ1: Reaction/Comment/Share | รอบ2: Reaction/Comment/Share |
| --- | --- | --- |
| P01 | 169/72/76 | 169/72/76 |
| P02 | ≈1,100/366/346 | ≈1,100/366/346 |
| P03 | 24/1/null | 24/1/null |
| P04 | 270/1/407 | 270/1/407 |
| P05 | 392/77/79 | 392/77/79 |
| P06 | 61/3/102 | 61/3/102 |
| P07 | ≈24,000/382/956 | ≈25,000/389/965 |
| P08 | 40/1/31 | 40/1/31 |
| P09 | 43/22/3 | 43/23/3 |
| P10 | 5/0/2 | 5/0/2 |

- Availabilityและcount sourceไม่เปลี่ยนทุกช่อง; P02/P05ใช้ embedded UFI summary ทั้งสองรอบ และ P10ใช้ scoped comment0 fallback ทั้งสองรอบ
- 4ค่าที่เปลี่ยนคือ P07ทั้ง3metricและ P09comment ซึ่ง raw textเปลี่ยนตามทั้งหมด ไม่พบความต่างที่เกิดจาก parserใน replayนี้
- Replay snapshotใหม่20/20ชุดให้ count/raw/source/evidenceเหมือน live outputs; replay postfix10ชุดก่อนหน้าไม่เปลี่ยนเช่นกัน
- Coverage96.7%ทั้งสองรอบ ไม่ใช่ accuracy96.7%: ไม่มี human referenceใหม่ตรงเวลา และ body-wide target scopeยังเป็นข้อจำกัดเดิม P05 textยังpreview_only
- Tests42/42ผ่านหลังจบ และ git diff --checkผ่าน

SHA-256 ก่อน/ระหว่าง/หลังเก็บตรงกัน:

```text
probe_post.py      a72e11f604bfa58742780bce23b04847efee083edbeddda6870b140450e3ae09
inspect_browser.py ba9e2f27b42698ccda0883dea1f2ee4a843df4568f2b6555151b5f679bf65652
```

จบรอบทดลองตามแผนแล้ว ยังไม่ปิด accuracy issue หรือสรุป tolerance/production readiness ต่อมาตรวจต้นทางได้ P03 Share=0 ตามหัวข้อด้านบน

## Opaque-pfbid fallback และ live validation — 18 ต.ค. 2026

เพิ่ม route → story → post → feedback identity chain สำหรับ URL แบบ opaque `pfbid` แล้ว ตัว parser เติมเฉพาะ counter ที่ body อ่านไม่ได้ และคืน `null` เมื่อ route, story, feedback, subscription target หรือ summaries ขัดกัน

Share summary ต้องมี `is_empty` แบบ boolean และสอดคล้องกับ count:

- `count=0` ต้องเป็น `is_empty=true`
- `count>0` ต้องเป็น `is_empty=false`
- ค่า missing, ไม่ใช่ boolean หรือขัดกับ count ให้คืน `null`

ก่อนแก้ tests ใหม่ล้ม 7 cases ตามที่คาด หลังแก้ focused tests ผ่าน 14/14 และ suite ผ่าน 50/50

เก็บ live ใหม่หนึ่งครั้งต่อ URL แบบ anonymous ผ่านคิวเดียว เว้น 21 วินาที ไม่มี retry ทั้งคู่ HTTP 200 และ source hashes ไม่เปลี่ยน:

| Sample | เวลา UTC | Body Reaction/Comment/Share | Embedded Comment/Share | ผล collector |
| --- | --- | --- | --- | --- |
| P03 | 18:41:13 | 24/4/ไม่แสดง | 4/0 | 24/4/0 |
| P04 | 18:41:36 | 275/1/414 | 1/414 | 275/1/414 |

ค่าบวกของ embedded summary ตรงกับ body ทุกช่องที่เทียบได้ และ offline replay ตรงกับ live ทั้ง count/raw/source/evidence ส่วน P03 Share=0 ยังไม่มี label บน body จึงอาศัย identity-scoped summary กับ reference เดิม

หลักฐานรอบนี้อยู่ใน ignored `runs/live-opaque-pfbid-20261018T184108Z-*` และ `runs/live-opaque-pfbid-20261018T184134Z-*` ไม่ upload full page content

## หลักฐาน local

ไฟล์เหล่านี้อยู่ใน ignored `experiments/facebook_posts/runs/` ไม่ upload full page/post/comment content:

- `p03-share-debugger.txt`
- `p03-share-diagnosis-initial.json`, `p03-share-diagnosis-ledger.json`
- `p03-p04-identity-chains.json`, `p03-p04-requested-token-trace.json`, `p03-p04-route-info.json`
- `counter-repeat-20261012T085728Z-summary.json`, `-comparison.json` และ per-URL snapshots
- `counter-followup-postfix-replay.json`
- `p03-share-user-confirmation.json` (referenceจากผู้ใช้; ผล collectorเดิมไม่เปลี่ยน)

ยังต้องแยก coverage, target scope และ human accuracy โดยเฉพาะ body-wide Reaction/Share และค่าประมาณ P02/P07 ไม่สรุป tolerance หรือ production readiness จากชุดเล็กนี้
