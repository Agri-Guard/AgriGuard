# AgriGuard

**Agricultural Intelligence System for Uganda**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

### Overview

**AgriGuard** is an intelligent agricultural platform designed to strengthen **food security, farmer incomes, and agro-input quality** in Uganda.

It combines **machine learning**, **data analytics**, and **user-friendly dashboards** to solve critical challenges faced by Ugandan farmers and policymakers.

---

### Problem Statement

Farmers in Uganda continue to struggle with:
- High **crop price volatility** leading to income uncertainty
- Widespread **counterfeit seeds, fertilizers, and pesticides**
- Limited access to timely **market intelligence**
- Climate and production risks

---

### Solution

AgriGuard delivers **data-driven insights** through:

- **Accurate crop price forecasting** using Machine Learning
- **Counterfeit agro-input detection** system
- **Market risk analysis** and intelligence dashboard
- Decision support tools for **farmers**, **agribusinesses**, and **government**

---

### Key Features (MVP)

- **Price Forecasting Engine** — Predict future prices for major Ugandan crops (maize, matooke, coffee, beans, cassava, etc.)
- **Fake Input Detector** — Verify authenticity of seeds, fertilizers, and pesticides
- **Interactive Dashboard** — Built with Streamlit for easy visualization and insights
- **Backend API** — FastAPI for scalable and secure data access
- **Data Pipeline** — Structured processing of raw agricultural data

---

### Tech Stack

| Layer              | Technologies                          |
|--------------------|---------------------------------------|
| **Backend**        | FastAPI, Python                       |
| **Frontend**       | Streamlit                             |
| **ML / Data**      | scikit-learn, pandas, NumPy, Matplotlib, Seaborn |
| **Infrastructure** | Docker, Docker Compose                |
| **Development**    | VS Code, Jupyter Notebooks            |

---

### 📁 Project Structure

```bash
AgriGuard/
├── backend/              # FastAPI Application
├── frontend/             # Streamlit Dashboard
├── ml/                   # Machine Learning models & training
│   ├── training/
│   ├── inference/
│   └── models/
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
├── notebooks/            # Exploratory Data Analysis
├── scripts/              # Utility & automation scripts
├── docs/                 # Documentation
├── config/
├── tests/
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md


Quick Start
Using Docker (Recommended)
Bash# 1. Clone the repository
git clone https://github.com/Agri-Guard/AgriGuard.git
cd AgriGuard

# 2. Copy environment variables
cp .env.example .env

# 3. Start the application
docker-compose up --build
Manual Setup
Bash# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (in new terminal)
cd frontend
pip install -r requirements.txt
streamlit run Home.py

Future Roadmap

Weather-integrated yield prediction
Satellite imagery analysis
SMS & USSD alerts for farmers
Mobile app (PWA)
National Food Security Index
Integration with UBOS and Ministry of Agriculture data


Authors
Keith Ndiema Kissa (Lead)
Biyimbwa Elijah Ssimwogerere
Lukwago Mahad

We are students @ Mbarara University of Science and Technology (MUST)

License
This project is licensed under the MIT License — see the LICENSE file for details.

Contributing
Contributions, issues, and feature requests are welcome!
Feel free to check the issues page.

Made with ❤️ for Ugandan Farmers & Food Security