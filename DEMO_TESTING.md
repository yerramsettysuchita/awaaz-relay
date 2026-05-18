# Awaaz Relay — Demo Testing Guide

Generate all test materials using Claude (claude.ai) with the exact prompts below.
Save images as JPG/PNG and drop them into `data/government_sources/` for OCR testing.

---

## Part 1 — Sample Images for Upload/OCR Testing

Go to **claude.ai → attach nothing → paste the prompt → Claude describes the form**.
Then use **any image editor** (even Paint or Canva) to create a simple layout from the description.
Or ask Claude to give you HTML you can screenshot.

### Image 1 — Widow Pension Application Form (FORM 1-W)

Paste this into Claude:

```
Create an HTML page that looks like a Tamil Nadu government widow pension application form (FORM 1-W).
Include these sections with blank fill-in fields:
- Header: "GOVERNMENT OF TAMIL NADU — SOCIAL WELFARE DEPARTMENT"
- Subheader: "Application for Destitute Widow Pension Scheme (DWPS)"
- Applicant Name (in Tamil and English)
- Date of Birth, Age
- Husband's Name, Date of Death
- Annual Income
- Address (Door No, Street, Village, Taluk, District, Pincode)
- Aadhaar Number (partially hidden: XXXX-XXXX-1234)
- Bank Account Number, IFSC Code, Bank Name
- Documents attached checklist: ☐ Death Certificate ☐ Aadhaar ☐ Ration Card ☐ Bank Passbook ☐ Photo
- Declaration paragraph
- Signature line and Date
Use a clean government-form style with a light blue header, black text, and bordered table layout.
Make it look like a real scanned government form.
```

**Screenshot the result → save as** `form_widow_pension_blank.jpg`

---

### Image 2 — Filled Widow Pension Form (for OCR test)

```
Create an HTML page of a filled Tamil Nadu widow pension application form with this fake data:
- Name: Lakshmi Devi R
- Age: 34, Date of Birth: 12/03/1990
- Husband's Name: Rajan M, Date of Death: 15/08/2023
- Annual Income: ₹28,000 (daily wage labour)
- Address: 4/12 Kamaraj Street, Thanjavur Taluk, Thanjavur District - 613001
- Aadhaar: XXXX-XXXX-4521
- Bank: Indian Bank, Account: 7823456012, IFSC: IDIB000T123
- Documents checked: ☑ Death Certificate ☑ Aadhaar ☑ Ration Card ☑ Bank Passbook ☑ Photo
Use handwritten-style font for the filled-in parts to simulate a real submitted form.
Government form style with a light blue header.
```

**Screenshot → save as** `form_widow_pension_filled.jpg`

**Test by:** Upload this image in the Upload tab → ask "Is this person eligible?"

---

### Image 3 — Old Age Pension Application

```
Create an HTML page for a Tamil Nadu Old Age Pension (IGNOAPS) application form with fake filled data:
- Name: Murugesan K, Age: 67
- BPL Ration Card No: TN-14-023-456789
- Annual Income: None (incapacitated)
- Assets: One room house valued ₹40,000
- Address: 7 Anna Nagar, Kumbakonam Taluk, Thanjavur District
- Bank: SBI, IFSC: SBIN0007823
Government form style, partially filled in Tamil and English.
```

**Screenshot → save as** `form_old_age_pension.jpg`

---

### Image 4 — Disability Certificate (for disability pension test)

```
Create an HTML page showing a Tamil Nadu government medical disability certificate with fake data:
- Header: "GOVERNMENT OF TAMIL NADU — MEDICAL CERTIFICATE FOR DISABILITY"
- Patient Name: Selvam R
- Age: 28, Date: 18/05/2026
- Disability Type: Locomotor Disability (Lower limbs)
- Percentage of Disability: 55%
- Certified by: Dr. K. Anand, MBBS, Civil Hospital Thanjavur
- Certificate No: TN/THJ/DIS/2026/0847
Stamp and signature area. Government medical certificate style.
```

**Screenshot → save as** `certificate_disability.jpg`

**Test query:** "I have a 55% disability certificate. What pension can I get?"

---

### Image 5 — Rejected Application Letter (for appeal test)

```
Create an HTML page of a Tamil Nadu government rejection letter for a pension application:
- Letterhead: Office of the Special Tahsildar, Social Security Schemes, Thanjavur
- Date: 10/04/2026
- Subject: Rejection of Widow Pension Application — Ref No. TN/THJ/WPS/2026/3421
- Reason: "Annual income exceeds the prescribed limit of ₹2,40,000"
- Body: Formal government letter style explaining the rejection
- Signed by: Special Tahsildar, Thanjavur
- Note: "Appeal may be filed within 30 days to the District Collector"
Government letter style with a formal Tamil Nadu government letterhead.
```

**Screenshot → save as** `letter_rejection.jpg`

**Test query:** "My application was rejected because of income limit. The form says ₹28,000/year. What should I do?"

---

## Part 2 — Text Queries to Test All 5 Languages

Paste these directly into the text box on the website.

### Tamil (தமிழ்) — select Tamil language
```
என் கணவர் கடந்த ஆண்டு இறந்தார். நான் தினக்கூலி வேலை செய்கிறேன், மாதம் ₹3,500 சம்பாதிக்கிறேன். விதவை ஓய்வூதியம் கிடைக்குமா? என்ன ஆவணங்கள் வேண்டும்?
```
*(My husband died last year. I earn ₹3,500/month. Am I eligible for widow pension? What documents do I need?)*

```
எனக்கு ஆதார் அட்டை இல்லை. வாக்காளர் அட்டையுடன் விண்ணப்பிக்கலாமா?
```
*(I don't have Aadhaar. Can I apply with voter ID?)*

---

### Telugu (తెలుగు) — select Telugu
```
నా భర్త గత సంవత్సరం మరణించాడు. నేను రోజువారీ కూలీగా పని చేస్తాను, నెలకు ₹3,500 సంపాదిస్తాను. వితంతు పెన్షన్ వస్తుందా?
```

```
నా దరఖాస్తు తిరస్కరించబడింది. ఏమి చేయాలి?
```

---

### Kannada (ಕನ್ನಡ) — select Kannada
```
ನನ್ನ ಗಂಡ ಕಳೆದ ವರ್ಷ ತೀರಿಕೊಂಡರು. ನಾನು ದಿನಗೂಲಿ ಕೆಲಸ ಮಾಡುತ್ತೇನೆ, ತಿಂಗಳಿಗೆ ₹3,500 ಸಂಪಾದಿಸುತ್ತೇನೆ. ವಿಧವಾ ಪಿಂಚಣಿ ಸಿಗುತ್ತದೆಯೇ?
```

```
ವಿಕಲಚೇತನ ಪಿಂಚಣಿಗೆ ಏನು ದಾಖಲೆಗಳು ಬೇಕು?
```

---

### Hindi (हिंदी) — select Hindi
```
मेरे पति पिछले साल गुजर गए। मैं दिहाड़ी मजदूरी करती हूं, महीने में ₹3,500 कमाती हूं। क्या मुझे विधवा पेंशन मिल सकती है?
```

```
मेरी उम्र 63 साल है और मैं विधवा हूं। मुझे कौन सी पेंशन मिलेगी?
```

---

### English — select English
```
I am a widow. My husband died 8 months ago. I do daily wage work and earn ₹3,500 per month. I don't have an Aadhaar card but I have a voter ID. Am I eligible for the widow pension? What documents do I need?
```

```
My pension application was rejected. The letter says my income is too high, but I only earn ₹28,000 per year. What should I do? Can I appeal?
```

```
I am 67 years old. I am a widow with no income. My fixed assets are a small house worth ₹40,000. Do I qualify for old age pension or widow pension?
```

---

## Part 3 — Voice Input Test Phrases

Open the Voice tab (Chrome or Edge only) and speak these:

| Language | Say this |
|---|---|
| Tamil | "என் பெயர் லட்சுமி. நான் விதவை. விண்ணப்பிக்க என்ன வேண்டும்?" |
| Telugu | "నా పేరు సావిత్రి. నేను వితంతువు. దరఖాస్తు చేయడానికి ఏమి కావాలి?" |
| English | "I am a widow and I want to apply for widow pension. What documents do I need?" |
| Hindi | "मैं विधवा हूं और पेंशन के लिए आवेदन करना चाहती हूं। क्या करूं?" |

---

## Part 4 — Edge Cases to Verify Safety Gates

These should trigger the **red escalation card** (confidence < 40%):

```
Can I get a pension for my cow that died?
```
```
Tell me how to get money from the government for my business.
```
```
What is the weather in Chennai today?
```

These should show **medium confidence** with a warning banner:
```
I am a widow but I remarried and then my second husband also died. Can I still apply?
```

---

## Part 5 — Multi-Turn Conversation Test

Run these queries **one after another without resetting** to test conversation context:

1. "I am a widow aged 34. My husband died last year."
2. "My monthly income is ₹3,500 from daily wage work."
3. "I don't have an Aadhaar card. What alternative ID can I use?"
4. "Where exactly do I submit the form?"

The conversation thread panel should appear after query 2, showing prior turns. After 8 queries the turn counter turns amber and shows "Context full — Reset".

---

## Quick Reference — File Names for `data/government_sources/`

| File | Purpose | Test feature |
|---|---|---|
| `form_widow_pension_blank.jpg` | Blank FORM 1-W | Upload tab OCR |
| `form_widow_pension_filled.jpg` | Filled FORM 1-W | Upload + eligibility check |
| `form_old_age_pension.jpg` | Old age pension form | Upload + scheme detection |
| `certificate_disability.jpg` | Disability certificate | Upload + disability scheme |
| `letter_rejection.jpg` | Rejection letter | Upload + appeal guidance |
