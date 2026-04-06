🏦 Bank Reviews Lakehouse — End-to-End Data Engineering Project

🔧 Tech Stack:

🌐 Web Scraping — Selenium (automated extraction of 139+ real reviews from Google Maps)
🗂️ Data Lakehouse — Bronze / Silver / Gold architecture
🔄 Orchestration — Apache Airflow (daily automated pipeline)
🧠 NLP — TextBlob (sentiment analysis: Positive / Negative / Neutral)
🦆 Data Warehouse — DuckDB + dbt
📊 Visualization — Power BI (interactive dashboard)

📐 Architecture:

Google Maps → Selenium → JSON (Bronze)
→ Pandas + NLP → Parquet (Silver)
→ DuckDB + dbt → Gold KPIs
→ CSV Export → Power BI Dashboard

📊 Key Insights:

Analyzed 5 banking agencies with 139 real customer reviews
Average ratings range from ⭐ 1.36 to ⭐ 4.17 across branches
Sentiment analysis revealed that negative feedback dominates in most agencies
Fully automated pipeline running daily via Airflow
