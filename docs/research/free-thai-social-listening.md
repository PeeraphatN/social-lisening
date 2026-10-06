# Free Thai social listening: feasibility and beginner path

Researched: 2026-10-06. This is a feasibility guide, not an implemented collector.

**Current scope:** the user clarified that the company Page has no useful comments. The target is discussion in other public spaces about TKC. The managed-Page design below is therefore an earlier candidate, not the selected collection approach. See [TKC public-discussion findings](tkc-public-discussion.md) for the revised source map and recommendation.

## 1. What can be free?

A small prototype can use free software and run on a computer you already own. Electricity, internet, development time, and eventual production capacity still have costs. Free software does not guarantee permission to collect a platform's data.

| Data you want | Collection route | Assessment |
| --- | --- | --- |
| Thai news headlines and links | Publisher RSS/Atom feeds where available | Good starting point; validate each feed and its usage terms before choosing it. |
| Discovery of Thai news across publishers | GDELT DOC API | Free news data with language filtering; coverage is an index, not every article on the internet. |
| Comments on a Facebook Page you manage | Official Pages API | Relevant route to investigate; first prove access with a small test. Exact current permissions remain unverified in this research. |
| Comments on other public Facebook Pages | Investigate Page Public Content Access | Approval and use-case dependent; availability and comment coverage must be verified. Do not assume unrestricted access. |
| Comments on news websites | Publisher-specific API, feed, or expressly permitted extraction | Separate integration for each site. Article feeds do not establish access to reader comments. |

An API is an interface a service provides for programs to request data. RSS/Atom is a publisher-provided feed of updates. Scraping means extracting information from website pages.

## 2. News collection: recommended first milestone

**Publisher feeds:** Use feeds explicitly offered by each publisher, if available. Python's [feedparser documentation](https://feedparser.readthedocs.io/en/stable/introduction.html) describes downloading and parsing RSS/Atom and returning Unicode text. Start by retaining the title, link, source, and available date. Feed contents vary; do not assume article bodies or comments are included.

Candidate feed URLs were attempted for Khaosod, Matichon, and Prachatai, but the web reader could not retrieve them. **No specific Thai publisher feed was verified as working during this research.** Validate real feed XML, recent items, and publisher terms before implementation; a URL containing `feed` or `rss` alone is insufficient evidence.

**GDELT:** Its [official data page](https://gdeltproject.org/data.html) describes its database as free and open. The [DOC API documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) describes article-list output, JSON/RSS formats, and `sourcelang`/`sourcecountry` filters. Its [language list](https://data.gdeltproject.org/api/v2/guides/LOOKUP-LANGUAGES.TXT) includes Thai (`tha`).

Proposed first query: `flood sourcelang:thai`, with `mode=artlist` and `format=json`. This is a documented query shape, **not a live-tested request**. GDELT searches English machine translations, so use English topic keywords there. For exact Thai brand names and spelling variants, separately test matching against original Thai feed text. `sourcelang:thai` selects Thai-language articles; `sourcecountry:thailand` selects outlets located in Thailand, which is a different filter.

Use GDELT to discover article titles and URLs. Do not assume its open data status licenses republication of publisher-owned full articles, or that it supplies reader comments. Broad coverage and perfect recall have not been established.

## 3. Facebook: verify access before building around it

For a Page you manage, investigate a Page access token and permissions such as `pages_show_list`, `pages_read_engagement`, and `pages_read_user_content`. These are investigation leads, not a verified current permission recipe. Test reading one real post's comments before committing to the integration.

Official documentation to check:

- [Pages API getting started](https://developers.facebook.com/docs/pages-api/getting-started/).
- [Permissions reference](https://developers.facebook.com/docs/permissions/).
- [Object comments reference](https://developers.facebook.com/docs/graph-api/reference/object/comments/).
- [Page Public Content Access](https://developers.facebook.com/docs/features-reference/page-public-content-access/).

These developer pages returned HTTP 429 during research. Their exact current permissions, access levels, review criteria, rate limits, and pricing were not verified. For Pages you do not manage, investigate approved public-content access rather than assuming managed-Page permissions apply. A public URL alone does not demonstrate API authorization.

Meta's [independent research announcement](https://about.fb.com/news/2023/11/new-tools-to-support-independent-research/) confirms public Facebook comments in Meta Content Library/API and describes applications through ICPSR for qualified academic or nonprofit institutions conducting scientific or public-interest research. This is a potential research route, not evidence that an ordinary commercial web service qualifies. The same announcement says CrowdTangle ceased availability after August 14, 2024.

Meta describes enforcement against unauthorized automated extraction in its [scraping-for-hire announcement](https://about.fb.com/news/2022/07/actions-against-scraping-for-hire/). Recommendation: do not base the service on unauthorized Facebook browser scraping. An open-source scraper's license does not grant access to Meta's data.

## 4. Simple software and hosting choices

| Component | Suggested choice | Why |
| --- | --- | --- |
| Feed collector | Python + feedparser | Feed parsing and Unicode support; see the documentation above. |
| Local storage | SQLite | A database stored in a file; free public-domain software according to [SQLite](https://sqlite.org/about.html). |
| Thai text processing | PyThaiNLP | Word segmentation and Thai language utilities; its [official repository](https://github.com/PyThaiNLP/pythainlp) lists features and licenses. |
| Dashboard | Streamlit | A Python web dashboard; [Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud) offers free deployment. |
| Initial collection schedule | Run locally on demand | Avoid depending on continuous free cloud execution before the collector works. |

Start with keyword matches and mention counts. Add Thai segmentation when needed. Sentiment classification needs a separate model or rules and evaluation on real Thai examples; segmentation alone is not sentiment analysis. Keep full article text and unnecessary personal identifiers out of the initial dataset.

Separate collection from display. A local collector can save SQLite data and export a CSV for the demonstration dashboard. Do not treat a cloud demo's local filesystem as the only copy of historical data.

Free hosting has limits: Streamlit's [management documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app) says inactive apps sleep after 12 hours and describes resource limits. Recommendation: use it for the dashboard demonstration, not as a guaranteed continuous collection worker. A dependable service with many users and large historical datasets needs a separate capacity and cost assessment.

## 5. Beginner implementation sequence

1. **Choose one topic and its spelling variants.** Example: a brand name or a topic such as PM2.5. Estimate: 15 minutes to define the initial list.
2. **Prove one news source works.** Retrieve a small GDELT result or validate one publisher feed. Save title, source link, available date, and collection time. Estimate: 2-4 assisted development hours after the environment is ready.
3. **Build a small local dashboard.** Search Thai text, filter dates/sources, show mention counts, and export CSV. Estimate: 4-8 assisted development hours. These are planning estimates, not guarantees for someone learning Python from zero.
4. **Prove Facebook access independently.** Choose one managed Page or investigate approval for other Pages. Technical testing may take hours; approval time is unknown and should not be promised.
5. **Connect only validated sources.** Deduplicate records by source ID or URL, retain provenance, and test collection on multiple runs before considering continuous operation.

Immediate decision: do the required Facebook comments belong to a Page you manage, to other public Pages, or to both? Also confirm whether “news” means articles, reader comments, or both when specifying the first implementation.

## 6. Company-owned service: collection and sentiment design

Follow-up requirement: an internal company asset that tracks positive, negative, and neutral sentiment about the company. Research-only Meta access is not the proposed route. The design below is a recommendation, not implemented or tested behavior.

### Coverage comes first

Begin with a company Page whose manager authorizes access. Meta's [official Facebook API collection on Postman](https://www.postman.com/meta/facebook/documentation/r56bjfd/facebook-api?entity=request-23987686-0b79260c-96bd-49de-875b-6076213785fc) documents requesting `/me/accounts?fields=name,access_token,tasks` with a User access token to list managed Pages and obtain Page access tokens. This verifies the managed-Page token flow; it does not verify unrestricted public mention search or all comment fields.

The first deliverable should be proof that the app can retrieve one real customer comment from one authorized Page post. Do not treat success reading Page-authored posts as proof of success reading user comments. Investigate `pages_show_list`, `pages_read_engagement`, and `pages_read_user_content` in the current dashboard. App Review and business verification depend on the current app configuration, permissions, and access levels; do not assume production is authorized merely because a development test succeeds.

Newer official [comments documentation](https://developers.facebook.com/documentation/pages-api/comments-mentions) and [webhook documentation](https://developers.facebook.com/documentation/pages-api/webhooks-for-pages) were also inaccessible. Exact permission and webhook matrices remain unverified. Endpoint shapes below are implementation investigation leads, not a current verified recipe:

- `/{page-id}/posts`: investigate retrieving Page posts.
- `/{post-id}/comments`: investigate retrieving comments on those posts.
- `/{comment-id}/comments`: investigate replies.

This initial coverage measures conversation on the authorized Page. Discussions on other Pages, unrelated public profiles, groups, or news-site comment sections require separate permitted sources. The dashboard must state its actual coverage.

### Recommended pipeline

1. **Collect.** Start with polling, meaning periodic API requests. Try a 15-minute interval for a small Page and adapt to actual API limits. Follow pagination and retrieve replies separately as required. Revisit older active posts within a defined window; new-post collection alone misses later comments. Back off on throttling, record the last successful collection, and surface token failures.
2. **Store.** Use SQLite on a company-controlled computer initially. Retain source, Page/post/comment IDs, parent-comment ID, available creation time, collection time, text, and an available source link. Deduplicate by source comment ID. Reconcile accessible edits/deletions and handle required data deletion; avoid collecting unnecessary commenter identities. Keep tokens server-side, outside Git and browser code.
3. **Decide relevance.** Distinguish comments about the company/product/service from spam and unrelated conversation. Company-Page comments can refer to other topics; keyword matching alone does not settle this. Preserve the parent post as available context and keep unrelated items out of company sentiment percentages.
4. **Classify and review.** Predict positive, negative, or neutral, with a separate review status for ambiguity. Retain the model version, score, and any human correction. Scores are model outputs, not guaranteed probabilities of being correct. Keep original Thai text and emojis; apply preprocessing consistently with the selected model.
5. **Display.** Show daily relevant-comment counts, sentiment counts/shares, negative examples linked to their source, pending reviews, and data freshness. Distinguish model predictions from human-reviewed labels. Report the denominator and excluded items. These are comment counts, not unique customers or a representative measure of all Thai consumers.

Webhooks can be investigated after polling works. A webhook is an HTTP notification of a change. It requires a reachable HTTPS receiver, verification of incoming requests, deduplication, and recovery for missed notifications. Polling remains useful for reconciliation. Verify the currently available Page fields and subscription permissions rather than assuming a generic `comments` field exists.

### Free Thai sentiment approach

**Recommended baseline:** use scikit-learn character TF-IDF features plus logistic regression. TF-IDF turns short character patterns into numeric features, and logistic regression learns a label from examples. Character features avoid requiring space-separated Thai words. This is a low-compute baseline to benchmark, not a claim that it handles sarcasm or company-specific targets well. See [text feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html) and [logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html).

The [Wisesight Sentiment Corpus](https://github.com/PyThaiNLP/wisesight-sentiment) provides 26,737 Thai social-media messages under CC0 and explicitly permits use for any purpose. It has four labels: positive, neutral, negative, and question. Do not silently convert question examples into neutral: questions can contain praise or complaints. Use a documented label policy and company examples to train/evaluate the intended three-class task. The repository also warns that its sample is not statistically representative.

**Candidate upgrade:** compare a sentiment-fine-tuned WangchanBERTa checkpoint using the [PyThaiNLP tutorial](https://pythainlp.org/tutorials/notebooks/wangchanberta_getting_started_aireseach.html). The [base model card](https://huggingface.co/airesearch/wangchanberta-base-att-spm-uncased) distinguishes the base language model from its classification variants. The base checkpoint alone is not a ready-made sentiment classifier. Verify the exact downloaded weights' commercial license, tokenizer/preprocessing, and label mapping before adoption; the dataset license does not establish the model license.

Define sentiment toward the company explicitly. Examples: `สินค้าดี ส่งเร็ว` is positive toward a product/service; `ของเสีย ติดต่อใครไม่ได้` is negative; `สาขาเปิดกี่โมง` is ordinarily a neutral information request. `ดีมาก รอแค่สามชั่วโมงเอง` can be sarcastic and needs context. Mixed statements such as praise for the product but criticism of delivery should have a written annotation rule or a review flag.

For an initial evaluation, manually label approximately 200-300 authorized company comments, keeping a held-out portion that is never used to tune the model. Include complaints, questions, slang, emoji-only responses, mixed Thai/English, and off-topic items. Examine negative-class precision (how often predicted complaints are real complaints) and recall (how many real complaints are found), not accuracy alone. Group near duplicates or posts to reduce evaluation leakage. Expand the sample when rare classes have too few examples; 200-300 items is a starting diagnostic, not a production-quality guarantee.

### First milestone and ownership

Recommended milestone: one authorized Page, up to 100 accessible comments, stored without duplication and shown in an internal dashboard with source context and manually reviewable sentiment predictions. Success also requires visible collection freshness and clear failure reporting. API access and availability determine whether the target count is achievable.

Keep the app registration under company-controlled administration, subject to Meta's account requirements. Keep the repository, deployment accounts, credentials, backups, and labeling policy under company control. Use local/company infrastructure first if the zero-subscription constraint is strict. Production availability and staff time still cost money.
