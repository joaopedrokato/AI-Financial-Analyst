# AI Financial Analyst

SEC-powered financial analysis web application that combines validated financial data, 10-K evidence retrieval, deterministic analysis, and grounded generative AI.

**Version:** 1.0 — Portfolio Release

**Live App:** https://ai-financial-analyst-kato.streamlit.app

---

## Overview

AI Financial Analyst is a web application built to analyze public companies using real SEC filings.

The project combines:

- validated financial fundamentals
- historical performance analysis
- 10-K filing intelligence
- evidence retrieval from Management Discussion & Analysis
- grounded generative AI
- deterministic fallback analysis

The goal is to provide financial insights while reducing unsupported AI-generated claims.

---

## Why I Built This

This project was created to explore how generative AI can be used responsibly in financial analysis.

Instead of allowing the AI model to rely mainly on general knowledge, the application builds its answers from:

1. validated SEC financial data
2. calculated financial metrics
3. relevant evidence retrieved from company 10-K filings

This creates a more transparent and grounded financial analysis workflow.

---

## Key Features

- Search public companies by ticker
- Retrieve company information directly from SEC EDGAR
- Automatically identify the latest 10-K filing
- Extract validated annual financial data
- Analyze revenue and net income history
- Calculate key financial metrics
- Retrieve relevant evidence from 10-K filings
- Generate grounded AI financial analysis
- Ask financial questions in natural language
- Fall back to deterministic analysis when the AI service is temporarily unavailable

---

## Financial Metrics

The application currently calculates and analyzes:

- Revenue
- Net Income
- Total Assets
- Shareholders' Equity
- Revenue Growth
- Net Margin
- Return on Equity (ROE)

ROE is calculated using average shareholders' equity when the required historical data is available.

---

## How It Works

```text
Company Ticker
      ↓
SEC EDGAR
      ↓
Latest 10-K Filing
      ↓
Validated Financial Data
      ↓
Financial Metrics
      ↓
10-K Text Extraction
      ↓
MD&A Evidence Retrieval
      ↓
Grounded AI Context
      ↓
Google Gemini
      ↓
AI Financial Analyst Response
Grounded AI Design

The generative AI component is intentionally constrained.

Financial numbers used in responses come from validated SEC data.

Explanations about company performance are grounded in evidence retrieved from the company's 10-K filing.

The model is instructed to:

use only the provided financial data and filing evidence
avoid unsupported claims
distinguish validated financial information from textual evidence
state when there is insufficient information
avoid providing investment recommendations
avoid predicting future stock prices without supporting evidence
10-K Intelligence

The application retrieves the company's latest 10-K filing directly from SEC EDGAR.

The filing is cleaned and analyzed to identify relevant sections of Management Discussion & Analysis.

Evidence retrieval considers:

topic relevance
financial keywords
causal language
surrounding context
duplicate-content filtering

This allows the AI Analyst to connect financial results with explanations found in the company's own regulatory filing.

Validation & Reliability

The financial extraction pipeline was tested across multiple public companies, including:

Apple
Microsoft
NVIDIA
Tesla
Amazon
Meta
Alphabet
JPMorgan Chase
Bank of America
Walmart
Coca-Cola
Disney

The project also includes automated validation checks designed to prevent values from different fiscal periods or SEC filings from being mixed.

Reliability Features

The application includes:

financial period validation
SEC accession validation
filing-date validation
automated metric checks
API retry handling
deterministic fallback analysis
user-friendly error handling

Temporary AI API failures do not prevent the application from providing a basic financial analysis.

Technologies
Python
Streamlit
Pandas
Requests
BeautifulSoup
SEC EDGAR APIs
Google Gemini API
Google GenAI Python SDK
GitHub
Streamlit Community Cloud
Data Sources

Financial data and regulatory filings are retrieved from the U.S. Securities and Exchange Commission through SEC EDGAR.

The application uses sources such as:

SEC Company Facts
SEC Company Submissions
SEC 10-K filings

No manually entered financial statements are required.

Security

Sensitive credentials are not stored directly in the source code.

The deployed application uses environment variables and Streamlit Secrets for:

SEC contact email
Gemini API key

Credential files and local secrets are excluded from version control.

Limitations
The application currently focuses primarily on annual 10-K filings.
Financial availability depends on SEC XBRL reporting structure.
Different companies may use different XBRL tags.
AI explanations are limited to the financial data and filing evidence provided to the model.
Temporary third-party API availability may affect AI responses.
The application does not provide investment advice.
The application does not attempt to predict stock prices.
Project Status

v1.0 — Portfolio Release

The current version includes:

multi-company ticker search
SEC financial data extraction
automated financial validation
financial performance dashboard
10-K intelligence
evidence retrieval
grounded generative AI
interactive financial Q&A
retry and fallback mechanisms
public Streamlit deployment
Future Improvements

Potential future improvements include:

quarterly 10-Q analysis
cash flow statement metrics
additional valuation metrics
company comparison functionality
more advanced evidence ranking
financial charts and visualization improvements
Disclaimer

This project is for educational and portfolio purposes only.

It does not constitute financial or investment advice.
