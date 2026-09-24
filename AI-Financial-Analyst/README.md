# AI Financial Analyst

An AI-powered financial analysis application that retrieves, validates, and analyzes public company financial data directly from SEC filings.

The project combines structured financial data, automated financial analysis, SEC 10-K evidence retrieval, and grounded generative AI in an interactive Streamlit application.

## Overview

AI Financial Analyst was built to make public-company financial analysis more transparent and evidence-based.

Users can enter a U.S. stock ticker and the application automatically:

1. Identifies the company through SEC data.
2. Retrieves its latest 10-K filing.
3. Extracts financial information from SEC XBRL data.
4. Validates financial values against the selected filing and fiscal periods.
5. Calculates financial metrics and historical changes.
6. Retrieves relevant evidence from the company's Management's Discussion and Analysis (MD&A).
7. Uses generative AI to answer financial questions grounded in validated data and retrieved SEC evidence.

## Key Features

### SEC Financial Data

The application retrieves structured financial information directly from SEC EDGAR, including:

- Revenue
- Net Income
- Total Assets
- Stockholders' Equity

Each value is tied to the selected 10-K accession number and fiscal period.

### Financial Metrics

The application automatically calculates:

- Revenue Growth
- Net Income Growth
- Net Margin
- Return on Equity (ROE)

ROE is calculated using average stockholders' equity.

### Automated Financial Analysis

A deterministic analysis layer summarizes historical financial performance directly from validated financial metrics.

This functionality does not depend on a language model.

### 10-K Intelligence

The application downloads and processes the company's SEC 10-K filing and extracts the Management's Discussion and Analysis section.

A retrieval system identifies relevant passages based on the user's financial question, with additional weighting for topic relevance and causal language.

### Grounded AI Financial Analyst

Users can ask questions such as:

- Why did revenue increase?
- What affected gross margin?
- Why did operating expenses increase?
- What was the company's net income?

The generative AI receives only:

- validated financial metrics;
- relevant evidence retrieved from the company's 10-K.

Responses distinguish structured financial data from SEC narrative evidence using references such as:

- `[Validated Data]`
- `[Evidence 1]`
- `[Evidence 2]`

The system is designed to reduce unsupported financial claims and does not provide investment recommendations.

### AI Fallback

If the generative AI provider is temporarily unavailable, the application falls back to a deterministic response based on validated financial data.

## Data Pipeline

```text
Stock Ticker
     |
     v
SEC Company Database
     |
     v
Latest 10-K
     |
     +----------------------+
     |                      |
     v                      v
SEC XBRL Data          10-K Document
     |                      |
     v                      v
Data Validation          MD&A Extraction
     |                      |
     v                      v
Financial Metrics      Evidence Retrieval
     |                      |
     +----------+-----------+
                |
                v
         Grounded AI Context
                |
                v
        AI Financial Analyst
```

## Data Validation

The project includes safeguards designed to prevent financial values from different filings or fiscal periods from being mixed.

Financial observations are filtered using information such as:

- SEC accession number
- filing type
- fiscal period
- start date
- end date
- reporting unit

The project was robustness-tested across companies from multiple sectors.

## Technologies

- Python
- Streamlit
- pandas
- Requests
- Beautiful Soup
- SEC EDGAR / SEC XBRL data
- Google GenAI

## Security

Credentials are not stored directly in the source code.

The application supports environment variables during development and Streamlit Secrets for deployment.

Required secrets:

```text
SEC_EMAIL
GEMINI_API_KEY
```

## Limitations

- The project currently focuses on U.S. public companies available through SEC EDGAR.
- Financial-data availability depends on SEC filings and XBRL structure.
- MD&A formatting can vary between companies.
- Generative AI availability depends on the external model provider.
- The application is intended for financial analysis and educational purposes, not investment advice.

## Project Status

**Version 1.0 — Portfolio Release**

Core pipeline completed:

- Multi-company SEC search
- 10-K selection
- Financial-data validation
- Financial metrics
- Automated analysis
- MD&A extraction
- Evidence retrieval
- Grounded generative AI
- AI fallback
- Streamlit interface

## Disclaimer

This project is for educational and analytical purposes only and does not constitute investment advice.
