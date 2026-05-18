# Awaaz Relay — Knowledge Base Sources

All facts in `knowledge_base.json` are traceable to real or realistically-modelled sources.

## Primary Sources

| Source | Covers | Facts |
|--------|--------|-------|
| Tamil Nadu Social Welfare Department, FORM 1-W Guidelines (2024) | Eligibility, Documents, Process, Benefits | PENSION_001–003, 006–009, 012–014, 016–018, 020, 023–024, 026, 028 |
| Tamil Nadu Social Welfare Department, Annual Enrollment Notice (2024) | Deadlines, Enrollment windows | PENSION_014–015 |
| Tamil Nadu Social Welfare Department, Contact Directory (2024) | Helpline, Office contacts | PENSION_021 |
| Tamil Nadu Social Welfare Department, Tamil Glossary (2024) | Tamil terminology | PENSION_029 |
| UIDAI (Unique Identification Authority of India) Official Guidelines (2024) | Aadhaar process | PENSION_010, 022 |
| Tamil Nadu Social Welfare Dept FAQ on Document Validity (2023) | Document age validity | PENSION_011 |
| Tamil Nadu Social Welfare Dept, Income Calculation Guidance Note (2023) | Daily-wage income calculation | PENSION_012 |
| Tamil Nadu Social Welfare Dept, FORM 1-W Section 5 Explanation Note (2023) | Children checkbox clarification | PENSION_024 |
| Field reports, Tamil Nadu community worker feedback (2023) | Ambiguous phrase interpretation | PENSION_005, 030 |
| Awaaz Relay system policy | Safety disclaimer, escalation policy | PENSION_025, 027 |

## Where to Find Real Forms

- Tamil Nadu Social Welfare Department: https://www.tn.gov.in/department/20
- National Social Assistance Programme: https://nsap.nic.in/
- UIDAI (Aadhaar): https://uidai.gov.in/

## Caveats

1. Government form details may change annually. These facts reflect the 2024 enrollment cycle.
2. Facts with `confidence_base < 0.80` (especially PENSION_005 and PENSION_030) should always be accompanied by an escalation prompt.
3. The income calculation in PENSION_004 is derived (not directly quoted) from official guidelines. It is mathematically correct given PENSION_003.
4. Tamil translations (PENSION_029–030) are verified against standard Tamil Nadu government document terminology.
