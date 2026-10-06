# TKC: public-discussion sources and a free starting approach

Researched: 2026-10-06. Scope: a company-owned tool for sentiment about the company in public spaces, rather than comments on its own Facebook Page. No collector has been implemented and no live Facebook comment corpus was obtained.

## Identity and search vocabulary

The supplied company name matches the listed company **บริษัท เทิร์นคีย์ คอมมูนิเคชั่น เซอร์วิส จำกัด (มหาชน)**, English **Turnkey Communication Services Public Company Limited**, stock symbol **TKC**. This identity is supported by the [SET company snapshot](https://lssmedia.setlink.set.or.th/2026/6M/TKC-6M69-ListedCompanySnapshot-TH.html). The company's site is [tkc-services.com](https://www.tkc-services.com/th/contact-us).

Recommended discovery groups:

| Group | Queries to try | Interpretation |
| --- | --- | --- |
| Exact Thai identity | `"เทิร์นคีย์ คอมมูนิเคชั่น"` | Strong company-name match. |
| English variants | `"Turnkey Communication Services"`, `"Turnkey Communication Service"` | Test both singular/plural forms. |
| Short name | `"TKC" "หุ้น"`, `"TKC" "โทรคมนาคม"` | Require context; TKC alone also finds unrelated products and organizations. |
| Project topic | `"TH-AI Passport"`, `"TH AI Passport"`, `"AI Passport"` | Related-project discovery, not proof that a comment targets TKC. |
| Consortium topic | `"กิจการค้าร่วมทีเอช"`, `"TH Consortium"` plus company/project context | Related entity; retain which member or topic the item actually discusses. |

These are proposed search queries, not a guarantee of recall or ongoing index access. Do not automatically count mentions of other firms as TKC mentions.

## Concrete public sources found

| Source | Evidence obtained | Collection status |
| --- | --- | --- |
| [Thai PBS Policy Watch: TH-AI Passport debate](https://policywatch.thaipbs.or.th/article/government-333) | Article dated 12 June 2026 identifies TKC in TH Consortium and reports debate about the project. | Article text accessible. Establishes company-linked coverage, not a reader-comment corpus. |
| [Pantip: IT workers discussing TH AI Passport](https://pantip.com/topic/44123432) | Search-indexed question post about the project's budget and usefulness. | Direct reader redirected to a contact/restriction page; full replies and current counts not verified. |
| [The Momentum: TH-AI Passport investigation](https://themomentum.co/feature-planb-ooh-ai-passport/) | Article names TKC and references two Facebook posts. Reports observations and disputed issues, not established wrongdoing. | Article accessible; direct Facebook text/comments unavailable. |
| [YOU SAY / HR SAY: TKC employee review](https://www.yousayhrsay.com/th/company/turnkey-communication-services-public-company-limited-17382/yousay) | One visible employee review dated 6 January 2023 contains favorable aspects and reservations. | Actual review text accessible. Historical employee opinion, not customer feedback or current company-wide sentiment. |
| [efinanceThai TV: TKC Executive Talk](https://www.youtube.com/watch?v=QDAp5V8w9CQ) | Indexed video dated 13 January 2022 about TKC and its business. | A video seed; audience comment availability/text not verified. |

Additional project-discussion seeds: [Pantip technical-analysis post](https://pantip.com/topic/44124278), [Pantip procurement-debate post](https://pantip.com/topic/44133539), and [Pantip post reproducing Facebook project observations](https://pantip.com/topic/44109187). Search snippets identified these posts; direct extraction of their comment threads failed. Some post bodies reproduce news or AI-generated analysis, so they are not automatically independent customer opinions.

Facebook reference seeds from The Momentum:

- [Referenced Facebook post 1](https://www.facebook.com/share/p/1BKQZhmA3v/?mibextid=wwXIfr).
- [Referenced Facebook post 2](https://www.facebook.com/share/p/1Q7NNuUXDv/).

Their authors, post dates, current availability, and actual reader comments were not verified. The article reports that a named individual made Facebook observations, but it does not establish which reference belongs to that individual. Treat these as links for manual inspection, not scraped sentiment evidence.

This search confirms public discussion of a company-linked project and at least one employee opinion. It does not establish complete coverage, platform volumes, or positive/negative percentages about TKC.

## Revised free approach

1. **Discover links.** Use manual searches and Google Alerts for the identity/project groups. Google's [Alerts documentation](https://support.google.com/websearch/answer/4815696?hl=en-GB) describes notifications of matching new search results. Alerts find indexed results; they are not a complete Facebook comment-search API. Publisher feeds and [GDELT](https://gdeltproject.org/data.html) can supplement news discovery, subject to real coverage tests.
2. **Keep source-specific access.** For each discovered page, record whether only a link/title is available, an authorized feed/API is available, or collection permission needs checking. Public visibility alone does not establish automated extraction rights. Do not evade blocked pages. The earlier managed-Page token flow does not solve collecting arbitrary third-party Facebook comments.
3. **Build a small evidence register.** Save URLs, dates when available, topic, direct company mention, source type, and a human-written summary. Use permissioned/licensed text for automated sentiment experiments. A register of leads is useful before a full comment corpus is available; clearly separate leads from collected comments.
4. **Label the target before sentiment.** Record whether a statement concerns TKC, the project, a government actor, another company, or has an unclear target. Separately record positive/negative/neutral and review status. Keep project-associated sentiment separate from company-directed sentiment. A critical article or complaint about public spending must not become an automatic negative-company label.
5. **Automate validated sources gradually.** Use Python, SQLite, and an internal dashboard after one source's access and usefulness are proven. Distinguish news reports, company announcements, investor opinions, employee reviews, and public comments. Deduplicate syndicated stories so one announcement copied across outlets does not inflate independent-public-opinion counts.

I did not verify a reliable, unrestricted, free, approved method for automatically collecting arbitrary third-party Facebook comments for this commercial tool. Investigating approved Meta public-content access remains separate from discovery; current eligibility and comment coverage are unverified. Meta's [research-tool announcement](https://about.fb.com/news/2023/11/new-tools-to-support-independent-research/) describes qualified institutional research access, which should not be assumed to cover this company asset.

### YouTube is a candidate requiring more than a quota check

YouTube's [commentThreads.list documentation](https://developers.google.com/youtube/v3/docs/commentThreads/list) documents retrieving threads for a video at one quota unit per request. Its [quota documentation](https://developers.google.com/youtube/v3/determine_quota_cost), updated 15 September 2026, describes separate daily limits of 100 search calls and 10,000 units combined for other endpoints. No API request was executed here.

However, the [developer policies](https://developers.google.com/youtube/terms/developer-policies), section III.E.4.h, restrict creating derived data/metrics from API data. Section III.L describes additional permissions for audited analytics developers. **Inference:** automatic sentiment labels/metrics from API comments need policy/permission assessment; free comment retrieval alone does not establish that this commercial sentiment use is allowed. Do not present YouTube as an unconditional replacement for Facebook sentiment collection. Storage refresh/deletion obligations also apply under those policies.

## First useful milestone

Build a register of 20 relevant public links, classify each as direct TKC discussion or related-project discussion, and identify which sources have usable permissioned comment data. The current evidence gives starting links, not 20 validated records or a finished sentiment dataset.

The revised pipeline is **public mention discovery → validated access → target identification → sentiment review → dashboard**. Company-Page administration is no longer the first dependency.
